#!/usr/bin/env bash
# Accel-Sim 冒烟验证 CI 脚本（Linux x86_64 / GitHub Actions ubuntu-24.04 直接可跑）
# 目标：4 架构配置 × 8 workload（rodinia_2.0-ft 内 8 个应用），trace-driven 仿真，收集 cycles，
#       输出 matrix_cycles.json（行=架构，列=workload，值=总 cycles，越小越好）。
#
# 背景：本脚本由 2026-10-14 冒烟尝试降级产生——本机 Apple Silicon + 慢速国际链路下，
#       镜像/依赖/trace 三处环境阻塞（详见 RESULT.md）。在正常网络与 Linux x86_64 环境预计 15-25 分钟跑完。
#
# 用法：bash run_accelsim_smoke.sh [输出目录（默认 ./ci-run）]
# 依赖：docker（首选，用官方预构建镜像）；无 docker 则本机自建（需要 CUDA_INSTALL_PATH 或 stub，见下）。
set -euo pipefail

# Actions runner 是非 root（sudo 可用）；容器/本机 root 下 sudo 自动为空
SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then SUDO=sudo; fi
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
OUT="${1:-ci-run}"
mkdir -p "$OUT"; cd "$OUT"

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
        git g++ libssl-dev libxml2-dev libboost-all-dev libgl-dev libzstd-dev python3
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
    # 已知坑（2026-10-14 实测记录 RESULT.md §2）：tracez_format.h 不在 include 路径
    cp -f util/tracer_nvbit/tracer_tool/tracez_format.h gpu-simulator/trace-parser/
    make -j"$(nproc)" -C ./gpu-simulator || {
        # 已知坑：-lzstd 在 .o 之前（GNU ld 左到右）→ 抓原链接行、末尾追加 -lzstd 补链
        echo "[build] make 失败，尝试 -lzstd 补链"
        LINK_LINE=$(make -C ./gpu-simulator 2>&1 | grep -m1 -E "g\+\+.*accel-sim\.out")
        echo "[build] link line: ${LINK_LINE:0:200]}"
        [ -n "$LINK_LINE" ] && sh -c "$LINK_LINE -lzstd"
    }
    test -f trace-parser/bin/release/accel-sim.out || { echo "[build] accel-sim.out 缺失"; exit 1; }
    ACCEL_SIM_ROOT="$PWD"
    cd "$OLDPWD/$OUT"
fi
cd "$ACCEL_SIM_ROOT"

# ---------- 2) traces：官方预收集 SASS traces（V100, rodinia_2.0-ft, 21MB 压缩/270MB 解压） ----------
echo "[2/5] 下载 V100 rodinia_2.0-ft traces"
mkdir -p hw_run
if [ ! -d hw_run/rodinia_2.0-ft ]; then
    wget -c https://engineering.purdue.edu/tgrogers/accel-sim/traces/tesla-v100/latest/rodinia_2.0-ft.tgz
    tar -xzf rodinia_2.0-ft.tgz -C hw_run
fi

# ---------- 3) 4 个架构配置：QV100 基线 + 3 个最小改动变体 ----------
echo "[3/5] 构造 4 个配置（只改 SM 数 / L2 大小）"
GPGPUSIM_CFG="$ACCEL_SIM_ROOT/gpu-simulator/gpgpu-sim/configs/tested-cfgs"
mk_variant() {  # $1=目录名 $2..=sed 规则
    local d="$GPGPUSIM_CFG/$1"
    rm -rf "$d"; cp -r "$GPGPUSIM_CFG/SM7_QV100" "$d"
    shift; for rule in "$@"; do sed -i "$rule" "$d/gpgpusim.config"; done
}
mk_variant SM7_QV100_80SM                                              # 基线：80 SM, L2 32(128:24)
mk_variant SM7_QV100_40SM      's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 40/' # SM 减半
mk_variant SM7_QV100_20SM      's/^-gpgpu_n_clusters 80/-gpgpu_n_clusters 20/' # SM 1/4
mk_variant SM7_QV100_80SM_L2h  's#^-gpgpu_cache:dl2 S:32:128:24#-gpgpu_cache:dl2 S:16:128:24#'  # L2 减半
cat >> util/job_launching/configs/define-standard-cfgs.yml <<'EOF'
QV100_80SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM/gpgpusim.config"
QV100_40SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_40SM/gpgpusim.config"
QV100_20SM:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_20SM/gpgpusim.config"
QV100_80SM_L2h:
    base_file: "$GPGPUSIM_ROOT/configs/tested-cfgs/SM7_QV100_80SM_L2h/gpgpusim.config"
EOF

# ---------- 4) 跑仿真：4 配置 × rodinia_2.0-ft（该套件含 8 个应用：backprop bfs hotspot lud nw srad streamcluster 等） ----------
echo "[4/5] 运行仿真（4 配置 × 全套件）"
set +u; source ./gpu-simulator/setup_environment.sh release; set -u   # set -u 与其未定义变量不兼容
for C in QV100_80SM QV100_40SM QV100_20SM QV100_80SM_L2h; do
    ./util/job_launching/run_simulations.py -C "$C-SASS" -B rodinia_2.0-ft \
        -T ./hw_run/rodinia_2.0-ft/9.1 -N "smoke-$C"
    ./util/job_launching/monitor_func_test.py -N "smoke-$C"    # 等待完成
done

# ---------- 5) 收集 cycles → matrix_cycles.json ----------
echo "[5/5] 收集结果"
python3 - "$OUT" <<'PYEOF'
import json, os, re, sys, glob
out = sys.argv[1]
sim_root = os.environ.get("ACCEL_SIM_ROOT", ".")
# accel-sim 结果目录：sim_run_*/<config>/<app>/*.gpgpusim.statistics.gz
stats = {}
for f in glob.glob(os.path.join(sim_root, "sim_run_*", "*", "*", "*")):
    pass  # 占位：实际路径由 run_simulations.py 生成，下面按更稳的定向 glob 收集
matrix = {}
for cfg in ("QV100_80SM", "QV100_40SM", "QV100_20SM", "QV100_80SM_L2h"):
    row = {}
    for st in glob.glob(f"sim_run_*/{cfg}-SASS/*/*.gpgpusim.statistics.gz"):
        app = os.path.basename(os.path.dirname(st))
        tot = 0
        import gzip
        with gzip.open(st, "rt", errors="ignore") as fh:
            for line in fh:
                m = re.match(r"gpgpu_n_tot_thrd_icount.*|gpu_tot_sim_cycle\s+=\s+(\d+)", line)
                if line.startswith("gpu_tot_sim_cycle"):
                    tot += int(line.split()[-1]); break
        if tot: row[app] = tot
    matrix[cfg] = row
apps = sorted(set().union(*[set(v) for v in matrix.values()]))
matrix = {k: {a: v.get(a) for a in apps} for k, v in matrix.items()}
json.dump(matrix, open(os.path.join(out, "matrix_cycles.json"), "w"), indent=1)
print("apps:", apps)
print("written:", os.path.join(out, "matrix_cycles.json"))
PYEOF
echo "完成。把 matrix_cycles.json 交给 analysis.py："
echo "  python3 analysis.py <ci-run 目录>/matrix_cycles.json"
