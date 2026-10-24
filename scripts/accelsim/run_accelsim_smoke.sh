#!/usr/bin/env bash
# Accel-Sim 冒烟验证 CI 脚本（Linux x86_64 / GitHub Actions ubuntu-24.04 直接可跑）
# 目标：8 架构配置 × 12 workload（llm-synth 合成 LLM 推理 kernel trace），trace-driven 仿真，
#       收集 cycles 与 time（cycles/核心时钟），输出 matrix_cycles.json + matrix_time_us.json
#       （行=架构，列=workload；time_us 为 2026-10-24 宇宙扩容轮的主读出，越小越好）。
#
# 背景：2026-10-22 LLM 合成 trace 矩阵判别信号成立（gemm SM +85.5%、attn-decode L2 +51.7%，
# K=3 贪心=strat_fix=穷举最优 1.000，K=2 方差导向漏 L2 维度）。本轮（2026-10-24 裁判指定）：
# 配置 4→8（+核心时钟 CLK566、+寄存器文件 RF 32K、+40SM/20SM×半L2 交叉项）、workload 5→12
# （GQA 剂量-响应 g8/g32、高占用 GEMM、纯依赖链 FFMA、共享 B-panel GEMM、batch-8 decode、混合）。
# 判据与假设预登记于 paper-ideas/experiments/20261023-dse-universe-expansion/PRE_REGISTRATION.md。
# trace 格式核验史（trace_parser.cc 字段级对齐、MAX_DST=1 教训）见 20261022-accelsim-llm-trace/。
#
# 用法：bash run_accelsim_smoke.sh [输出目录（默认 ./ci-run）]
# 依赖：docker（首选，用官方预构建镜像）；无 docker 则本机自建（需要 CUDA_INSTALL_PATH 或 stub，见下）。
set -euo pipefail

# Actions runner 是非 root（sudo 可用）；容器/本机 root 下 sudo 自动为空
SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then SUDO=sudo; fi
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
OUT="${1:-ci-run}"
REPO_ROOT="$(pwd)"          # 调用目录（CI=仓库根）；输出目录转绝对路径，防 cwd 漂移
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"; cd "$OUT"

# ---------- 1) 仿真器 ----------
# 首选官方预构建镜像（github.com/accel-sim/Dockerfile，nvidia/cuda:12.8-devel-ubuntu24.04 基座）
# 优先官方镜像；拉不动（manifest unknown 等）则回退源码自建。2026-10-20 实测
# GHCR 上无公开 accel-sim 镜像，Actions 上通常走源码自建路径（约 10-15 分钟）。
if command -v docker >/dev/null 2>&1 \
   && [ ! -f /.dockerenv ] \
   && docker pull -q ghcr.io/accel-sim/accel-sim-framework:latest >/dev/null 2>&1; then
    echo "[1/5] 使用官方 GHCR 镜像运行（内含已编译仿真器与 CUDA）"
    exec docker run --rm -v "$PWD:$PWD" -w "$PWD" \
        ghcr.io/accel-sim/accel-sim-framework:latest bash "$SCRIPT_PATH" "$PWD"
elif [ -f /.dockerenv ] && [ -d /accel-sim-framework ]; then
    ACCEL_SIM_ROOT="/accel-sim-framework"
else
    echo "[1/5] 无可用预构建镜像：源码自建"
    $SUDO apt-get update && DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y \
        wget build-essential xutils-dev bison zlib1g-dev flex libglu1-mesa-dev \
        git g++ libssl-dev libxml2-dev libboost-all-dev libgl-dev libzstd-dev python3 python3-psutil python3-pip
    cd ..
    git clone --recursive https://github.com/accel-sim/accel-sim-framework.git
    cd accel-sim-framework
    # setup_environment.sh 要求 CUDA_INSTALL_PATH/bin/nvcc 与 CUDA 头文件真实存在。
    # 【2026-10-14 实测教训】stub nvcc + pip nvidia-cuda-runtime-cu12 头文件【不够】：
    #   gpgpu-sim dev 分支编译报 incomplete type 'textureReference' / 'cuda_math' 成员缺失
    #   （pip 装的 CUDA12.9 头与期望的 toolkit 头不兼容）。必须装真 toolkit：
    DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y nvidia-cuda-toolkit
    export CUDA_INSTALL_PATH=/usr/lib/nvidia-cuda-toolkit/bin/..   # ubuntu 22.04: CUDA 11.5
    set +u; source ./gpu-simulator/setup_environment.sh release; set -u
    # 已知坑（2026-10-14 实测记录 RESULT.md §2）：
    # a) tracez_format.h 不在 include 路径 → 复制进 trace-parser；
    # b) Makefile LIBS 里 -lzstd 排在 $(BUILD_DIR)/*.o 之前（GNU ld 左到右）→
    #    在链接规则末尾追加 -lzstd。
    cp -f util/tracer_nvbit/tracer_tool/tracez_format.h gpu-simulator/trace-parser/
    # 注意：该行行尾带一个空格，锚点需容忍尾随空白
    sed -i 's#-o $(BIN_DIR)/accel-sim.out accel-sim.cc main.cc[[:space:]]*$#-o $(BIN_DIR)/accel-sim.out accel-sim.cc main.cc -lzstd#' gpu-simulator/Makefile
    make -j"$(nproc)" -C ./gpu-simulator
    test -f gpu-simulator/bin/release/accel-sim.out || { echo "[build] accel-sim.out 缺失"; exit 1; }
    ACCEL_SIM_ROOT="$PWD"
    cd "$REPO_ROOT"
fi
cd "$ACCEL_SIM_ROOT"

# ---------- 2) traces：llm-synth 合成 LLM 推理 kernel SASS traces（V100/SM7, ~130MB 文本） ----------
echo "[2/5] 生成 llm-synth traces（本地合成，无网络依赖）"
mkdir -p hw_run
GEN="$(dirname "$SCRIPT_PATH")/gen_llm_traces.py"
python3 "$GEN" hw_run

# ---------- 3) 8 个架构配置：SM 数 × L2 × 核心时钟 × RF（2026-10-24 宇宙扩容） ----------
echo "[3/5] 构造 8 个配置（SM 数 / L2 大小 / 核心时钟 / RF 大小）"
GPGPUSIM_CFG="$ACCEL_SIM_ROOT/gpu-simulator/gpgpu-sim/configs/tested-cfgs"
mk_variant() {  # $1=目录名 $2..=sed 规则
    local d="$GPGPUSIM_CFG/$1"
    rm -rf "$d"; cp -r "$GPGPUSIM_CFG/SM7_QV100" "$d"
    shift; for rule in "$@"; do sed -i "$rule" "$d/gpgpusim.config"; done
}
mk_variant SM7_QV100_80SM                                              # 基线：80 SM, L2 6MB, 1132MHz, RF 64K
mk_variant SM7_QV100_40SM      's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 40/' # SM 减半
mk_variant SM7_QV100_20SM      's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 20/' # SM 1/4
mk_variant SM7_QV100_80SM_L2h  's#^-gpgpu_cache:dl2 S:32:128:24#-gpgpu_cache:dl2 S:16:128:24#'  # L2 减半
# 新维度 1：核心时钟域减半（QV100 用绝对 MHz 四域 core:icnt:L2:DRAM，只降 core 域）
mk_variant SM7_QV100_80SM_CLKh 's/^-gpgpu_clock_domains 1132.0:1132.0:1132.0:850.0/-gpgpu_clock_domains 566.0:1132.0:1132.0:850.0/'
# 新维度 2：每 SM 寄存器文件减半（occupancy 经 trace 头 nregs 生效，shader.cc:4427）
mk_variant SM7_QV100_80SM_RFh  's/^-gpgpu_shader_registers 65536/-gpgpu_shader_registers 32768/'
# 交叉项：SM 数 × 半 L2
mk_variant SM7_QV100_40SM_L2h  's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 40/' 's#^-gpgpu_cache:dl2 S:32:128:24#-gpgpu_cache:dl2 S:16:128:24#'
mk_variant SM7_QV100_20SM_L2h  's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 20/' 's#^-gpgpu_cache:dl2 S:32:128:24#-gpgpu_cache:dl2 S:16:128:24#'
# trace-driven 侧还需要 gpu-simulator/configs/tested-cfgs/<cfg>/trace.config
TRACE_CFG="$ACCEL_SIM_ROOT/gpu-simulator/configs/tested-cfgs"
for V in SM7_QV100_80SM SM7_QV100_40SM SM7_QV100_20SM SM7_QV100_80SM_L2h \
         SM7_QV100_80SM_CLKh SM7_QV100_80SM_RFh SM7_QV100_40SM_L2h SM7_QV100_20SM_L2h; do
    mkdir -p "$TRACE_CFG/$V"; cp -f "$TRACE_CFG/SM7_QV100/trace.config" "$TRACE_CFG/$V/"
done
cat >> util/job_launching/configs/define-standard-cfgs.yml <<'EOF'
QV100_80SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM/gpgpusim.config"
QV100_40SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_40SM/gpgpusim.config"
QV100_20SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_20SM/gpgpusim.config"
QV100_80SM_L2h:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM_L2h/gpgpusim.config"
QV100_80SM_CLKh:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM_CLKh/gpgpusim.config"
QV100_80SM_RFh:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM_RFh/gpgpusim.config"
QV100_40SM_L2h:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_40SM_L2h/gpgpusim.config"
QV100_20SM_L2h:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_20SM_L2h/gpgpusim.config"
EOF
# 注册 llm-synth 套件（幂等：docker 再入时防重复追加）
JOBYML=util/job_launching/apps/define-all-apps.yml
grep -q "^llm-synth:" "$JOBYML" || cat >> "$JOBYML" <<'EOF'
llm-synth:
    exec_dir: "$ACCELSIM_ROOT"
    data_dirs: ""
    execs:
        - llm-gemm-prefill:
            - name: all
              args: ""
        - llm-attn-prefill:
            - name: all
              args: ""
        - llm-attn-decode:
            - name: all
              args: ""
        - llm-gemv-decode:
            - name: all
              args: ""
        - llm-elem:
            - name: all
              args: ""
        - llm-gemm-occu:
            - name: all
              args: ""
        - llm-attn-decode-g8:
            - name: all
              args: ""
        - llm-attn-decode-g32:
            - name: all
              args: ""
        - llm-gemm-tile:
            - name: all
              args: ""
        - llm-batch-decode:
            - name: all
              args: ""
EOF

# ---------- 4) 跑仿真：8 配置 × llm-synth（10 个合成 LLM kernel app） ----------
echo "[4/5] 运行仿真（8 配置 × llm-synth，10 app）"
set +u; source ./gpu-simulator/setup_environment.sh release; set -u   # set -u 与其未定义变量不兼容
for C in QV100_80SM QV100_40SM QV100_20SM QV100_80SM_L2h \
         QV100_80SM_CLKh QV100_80SM_RFh QV100_40SM_L2h QV100_20SM_L2h; do
    ./util/job_launching/run_simulations.py -C "$C-SASS" -B llm-synth \
        -T ./hw_run -N "smoke-$C"
    ./util/job_launching/monitor_func_test.py -N "smoke-$C"    # 等待完成
done

# ---------- 5) 收集 cycles → matrix_cycles.json + matrix_time_us.json ----------
echo "[diag] sim_run 目录树（文件级，深度不限）："
    find sim_run_* -type f 2>/dev/null | head -30 || true
    echo "[diag] cwd=$(pwd)"
echo "[5/5] 收集结果"
python3 - "$OUT" <<'PYEOF'
import json, os, sys, glob
out = sys.argv[1]
# 收集口径（2026-10-23 修复沿用）：trace-driven 模式逐 kernel 打印累计 gpu_tot_sim_cycle，
# 取每个 .o 文件最后一个值（= 全 app 总 cycles）。app 名取路径中 llm- 开头的组件。
# 2026-10-24 新增：time_us = cycles / 核心时钟 MHz——本轮配置含核心时钟差异（CLKh=566），
# gpu_tot_sim_cycle 按核心时钟域计数，跨时钟配置比较必须用时间（预登记 §1.2 主读出）。
CFGS = ("QV100_80SM", "QV100_40SM", "QV100_20SM", "QV100_80SM_L2h",
        "QV100_80SM_CLKh", "QV100_80SM_RFh", "QV100_40SM_L2h", "QV100_20SM_L2h")
CORE_MHZ = {c: 1132.0 for c in CFGS}
CORE_MHZ["QV100_80SM_CLKh"] = 566.0
matrix = {}
diag = []
for cfg in CFGS:
    row = {}
    outs = sorted(glob.glob(f"sim_run_*/**/{cfg}-SASS/**/*.o*", recursive=True))
    for st in outs:
        parts = os.path.normpath(st).split(os.sep)
        app = next((p for p in parts if p.startswith("llm-")), None)
        if app is None:
            continue
        last = 0
        with open(st, "rt", errors="ignore") as fh:
            for line in fh:
                if line.startswith("gpu_tot_sim_cycle"):
                    last = int(line.split()[-1])
        if last:
            row[app] = last
            diag.append(f"{cfg}\t{app}\t{last}\t{st}")
    matrix[cfg] = row
apps = sorted(set().union(*[set(v) for v in matrix.values()])) if matrix else []
matrix = {k: {a: v.get(a) for a in apps} for k, v in matrix.items()}
json.dump(matrix, open(os.path.join(out, "matrix_cycles.json"), "w"), indent=1)
tmatrix = {k: {a: (v[a] / CORE_MHZ[k] if v.get(a) else None) for a in apps}
           for k, v in matrix.items()}
json.dump(tmatrix, open(os.path.join(out, "matrix_time_us.json"), "w"), indent=1)
open(os.path.join(out, "collect_diag.txt"), "w").write("\n".join(diag) + "\n")
print("apps:", apps)
print("written:", os.path.join(out, "matrix_cycles.json"),
      "and", os.path.join(out, "matrix_time_us.json"))
if not apps:
    print("WARNING: no cycles collected; see find dump above and job logs", file=sys.stderr)
    sys.exit(1)
PYEOF
echo "完成。把 matrix_time_us.json（主读出）交给 analysis_univ.py："
echo "  python3 analysis_univ.py <ci-run 目录>/matrix_time_us.json"
