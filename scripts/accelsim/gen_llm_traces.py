#!/usr/bin/env python3
"""Synthesize Accel-Sim SASS-format traces for LLM inference kernels (V100/SM7).

Why: Purdue's public trace server has no LLM/DNN suite (cutlass.tgz et al. are
404 as of 2026-10-23; only cudasdk/rodinia/ubench remain), NVBIT capture needs a
real GPU (CI runners have none), and the accel-sim dev-branch "ml-workloads"
traces live on an internal Purdue scratch depot. This generator emits traces in
the exact text .traceg format the trace-parser consumes (verified against
trace_parser.cc @ dev and the official rodinia_2.0-ft traces), with instruction
mixes / address streams parameterized to LLM inference kernel characteristics:

  llm-gemm-prefill  register-tiled dense GEMM (prefill MLP/QKV): long FFMA runs
                    between sparse L2-resident loads -> compute-issue bound,
                    expected strongly SM-count sensitive, L2-size insensitive.
  llm-attn-prefill  flash-attention-like tile loop: LDG+FFMA+MUFU(EX2/RCP) mix,
                    L2 tile sharing across CTAs, moderate AI -> mixed bound.
  llm-attn-decode   GQA decode KV scan: 16 groups x 8 warps share 288KB KV
                    slices; aggregate concurrent footprint ~4.6MB (between
                    L2h 3MB and baseline 6MB) -> L2-capacity sensitive.
  llm-gemv-decode   decode GEMV over weights: 64MB unique streaming, no reuse
                    -> DRAM-BW bound control (expected SM/L2 insensitive).
  llm-elem          layernorm/activation elementwise: streaming low-AI control.

Caveats (documented in RESULT.md): addresses/instruction streams are synthetic
(no functional values are tracked by trace-driven replay); tensor-core HMMA is
deliberately avoided (FFMA emulation keeps opcode risk zero); only opcodes seen
in rodinia_2.0-ft traces (simulated successfully on QV100 2026-10-21) are used.

Usage: python3 gen_llm_traces.py <hw_run_root>   (writes <root>/llm-synth/9.1/...)
"""
import os
import sys

MASK = "ffffffff"
BASE_W = 0x00007F0000000000      # weights / KV / activations regions (device ptrs)
BASE_ACT = 0x00007F1000000000
BASE_KV = 0x00007F2000000000
BASE_OUT = 0x00007F3000000000


class TraceWriter:
    """Emits one kernel .traceg file in the accel-sim text format."""

    def __init__(self, path, name, kid, grid, block, shmem, nregs):
        self.f = open(path, "w", buffering=1 << 22)
        self.f.write(f"-kernel name = {name}\n")
        self.f.write(f"-kernel id = {kid}\n")
        self.f.write(f"-grid dim = ({grid[0]},{grid[1]},{grid[2]})\n")
        self.f.write(f"-block dim = ({block[0]},{block[1]},{block[2]})\n")
        self.f.write(f"-shmem = {shmem}\n")
        self.f.write(f"-nregs = {nregs}\n")
        self.f.write("-binary version = 70\n")
        self.f.write("-cuda stream id = 0\n")
        self.f.write("\n")
        self.f.write("#traces format = threadblock_x threadblock_y threadblock_z"
                     " warpid_tb PC mask dest_num reg_dests opcode src_num"
                     " reg_srcs mem_width mem_addresses\n\n")

    def begin_tb(self, tb):
        self.f.write("#BEGIN_TB\n\n")
        self.f.write(f"thread block = {tb[0]},{tb[1]},{tb[2]}\n\n")

    def warp(self, wid, lines):
        self.f.write(f"warp = {wid}\n")
        self.f.write(f"insts = {len(lines)}\n")
        self.f.write("\n".join(lines))
        self.f.write("\n")

    def end_tb(self):
        self.f.write("#END_TB\n")

    def close(self):
        self.f.close()


class Emitter:
    """Per-warp instruction line builder."""

    def __init__(self):
        self.lines = []
        self.pc = 0

    def _pc(self):
        p = self.pc
        self.pc += 0x10
        return f"{p:04x}"

    def op(self, dsts, opcode, srcs):
        d = dsts if isinstance(dsts, list) else [dsts]
        s = srcs if isinstance(srcs, list) else [srcs]
        self.lines.append(
            f"0 0 0 0 {self._pc()} {MASK} {len(d)} "
            + " ".join(f"R{r}" for r in d)
            + f" {opcode} {len(s)} "
            + " ".join(f"R{r}" for r in s)
            + " 0"
        )

    def mem(self, opcode, dsts, srcs, base, stride, width):
        d = dsts if isinstance(dsts, list) else ([dsts] if dsts else [])
        s = srcs if isinstance(srcs, list) else [srcs]
        self.lines.append(
            f"0 0 0 0 {self._pc()} {MASK} {len(d)} "
            + " ".join(f"R{r}" for r in d)
            + f" {opcode} {len(s)} "
            + " ".join(f"R{r}" for r in s)
            + f" {width} 1 0x{base:016x} {stride} 0"
        )

    def exit(self):
        self.op([], "EXIT", [])


def addr_math(e, out=4, n=6):
    """Address-computation prologue (IMAD/IADD3), like real compiled kernels."""
    for i in range(n):
        if i % 2 == 0:
            e.op([out + (i % 3)], "IMAD", [255, 255, 255])
        else:
            e.op([out + (i % 3)], "IADD3", [out + ((i - 1) % 3), 255, 255])


# --------------------------------------------------------------------------
# 1) llm-gemm-prefill: register-tiled GEMM, compute-issue bound
# --------------------------------------------------------------------------
def gen_gemm_prefill(appdir):
    ncta, nwarps = 96, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z17llm_gemm_prefillPfS_S_ii", 1, (ncta, 1, 1),
                    (128, 1, 1), 8192, 96)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            cta_base = BASE_W + cta * 32768 + wp * 4096
            for k in range(16):                       # load A/B tiles: 8KB
                e.mem("LDG.E.128", [16 + k],
                      [4], cta_base + k * 512, 16, 16)
            for it in range(8):                       # long FFMA runs on regs
                for j in range(512):
                    acc = j % 8
                    a = 16 + ((j // 8) % 32)
                    b = 48 + ((j // 8) % 32)
                    # operand regs are scoreboard deps only (trace-driven timing); MAX_DST=1
                    e.op([acc], "FFMA", [acc, a, b])
                e.mem("LDG.E.128", [16], [4],
                      cta_base + 16384 + it * 512, 16, 16)
            for j in range(4):                        # reduce accs
                e.op([8 + j], "FADD", [2 * j, 2 * j + 1])
            for j in range(4):                        # store C tile
                e.mem("STG.E.SYS", [], [8 + j // 2, 12],
                      BASE_OUT + cta * 4096 + wp * 1024 + j * 256, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


# --------------------------------------------------------------------------
# 2) llm-attn-prefill: flash-attention-like tile loop, mixed compute/memory
# --------------------------------------------------------------------------
def gen_attn_prefill(appdir):
    ncta, nwarps = 128, 4
    ntiles, tile_sz = 16, 262144       # 16 x 256KB shared K/V tiles = 4MB window
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z16llm_attn_prefillPfS_S_iii", 1, (ncta, 1, 1),
                    (128, 1, 1), 4096, 80)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            q = BASE_ACT + cta * 1024 + wp * 256      # Q fragments (private)
            for k in range(4):
                e.mem("LDG.E.128", [16 + k],
                      [4], q + k * 512, 16, 16)
            for it in range(32):
                tile = (cta + it) % ntiles            # L2-shared K/V tiles
                kv = BASE_KV + tile * tile_sz + wp * 8192 + (it % 64) * 512
                e.mem("LDG.E.128", [32], [4], kv, 16, 16)
                e.mem("LDG.E.128", [36], [4], kv + tile_sz // 2, 16, 16)
                for j in range(12):                   # QK^T partial dot
                    e.op([j % 8], "FFMA", [j % 8, 16 + (j % 16), 32 + (j % 4)])
                e.op([10], "MUFU.RCP", [0])           # softmax: max/div
                e.op([11], "MUFU.EX2", [10])          # exp
                e.op([12], "FADD", [11, 255])
                for j in range(8):                    # PV accumulation
                    e.op([j], "FFMA", [j, 36 + (j % 4), 11])
            e.mem("STG.E.SYS", [], [0, 12], BASE_OUT + cta * 512 + wp * 128, 4, 4)
            e.mem("STG.E.SYS", [], [1, 12], BASE_OUT + cta * 512 + wp * 128 + 4, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


# --------------------------------------------------------------------------
# 3) llm-attn-decode: GQA KV scan with cross-warp reuse, L2-capacity sensitive
#    16 groups x 2 CTA x 4 warps share 288KB slices -> ~4.6MB live footprint
#    (L2h=3MB thrashes; baseline 6MB holds it).
# --------------------------------------------------------------------------
def gen_attn_decode(appdir):
    ncta, nwarps = 32, 4
    groups, slice_sz = 16, 288 * 1024
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z15llm_attn_decodePfS_S_ii", 1, (ncta, 1, 1),
                    (128, 1, 1), 2048, 64)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            grp = (cta * nwarps + wp) // 8            # 8 warps per group
            lane = (cta * nwarps + wp) % 8
            sl = BASE_KV + grp * slice_sz
            for it in range(72):                      # warp + its 7 siblings hit
                off = ((it * 8 + lane) * 512) % (slice_sz - 512)
                e.mem("LDG.E.128", [16], [4], sl + off, 16, 16)
                e.op([0], "FFMA", [0, 16, 17])        # QK score accum
                e.op([1], "FFMA", [1, 18, 19])        # V accum
            e.op([8], "FADD", [0, 255])               # softmax scale
            e.op([9], "MUFU.EX2", [8])
            e.op([2], "FFMA", [1, 9, 8])
            e.mem("STG.E.SYS", [], [2, 12], BASE_OUT + grp * 512 + lane * 64, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


# --------------------------------------------------------------------------
# 4) llm-gemv-decode: streaming GEMV over weights, DRAM-BW bound control
# --------------------------------------------------------------------------
def gen_gemv_decode(appdir):
    ncta, nwarps = 64, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z14llm_gemv_decodePfS_S_i", 1, (ncta, 1, 1),
                    (128, 1, 1), 1024, 64)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            wid = cta * nwarps + wp                   # 256 warps x 256KB = 64MB
            base = BASE_W + wid * 262144
            for it in range(512):
                e.mem("LDG.E.128", [16], [4], base + it * 512, 16, 16)
                e.op([0], "FFMA", [0, 16, 17])        # 2 FLOP / 16B*32lane
                if it % 64 == 63:
                    e.op([1], "FADD", [0, 1])
            e.mem("STG.E.SYS", [], [0, 12], BASE_OUT + wid * 16, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


# --------------------------------------------------------------------------
# 5) llm-elem: layernorm/activation elementwise, streaming control
# --------------------------------------------------------------------------
def gen_elem(appdir):
    ncta, nwarps = 128, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z8llm_elemPfS_i", 1, (ncta, 1, 1), (128, 1, 1), 512, 48)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            base = BASE_ACT + (cta * nwarps + wp) * 16384
            for it in range(64):
                a = base + it * 256
                e.mem("LDG.E.SYS", [16], [4], a, 4, 4)
                e.op([0], "FADD", [16, 16])           # residual add
                e.op([1], "MUFU.EX2", [0])            # activation
                e.op([2], "FADD", [1, 255])
                e.mem("STG.E.SYS", [], [2, 12], a + 8388608, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


APPS = [
    ("llm-gemm-prefill", gen_gemm_prefill, [
        ("MemcpyHtoD", BASE_W, 33554432), ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("llm-attn-prefill", gen_attn_prefill, [
        ("MemcpyHtoD", BASE_KV, 4194304), ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("llm-attn-decode", gen_attn_decode, [
        ("MemcpyHtoD", BASE_KV, 4718592), ("MemcpyHtoD", BASE_ACT, 65536)]),
    ("llm-gemv-decode", gen_gemv_decode, [
        ("MemcpyHtoD", BASE_W, 67108864), ("MemcpyHtoD", BASE_ACT, 16384)]),
    ("llm-elem", gen_elem, [
        ("MemcpyHtoD", BASE_ACT, 8388608)]),
]


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "hw_run"
    suite = os.path.join(root, "llm-synth", "9.1")
    for name, fn, copies in APPS:
        appdir = os.path.join(suite, name, "all")
        os.makedirs(os.path.join(appdir, "traces"), exist_ok=True)
        fn(appdir)
        with open(os.path.join(appdir, "traces", "kernelslist.g"), "w") as kl:
            for _, addr, sz in copies:
                kl.write(f"MemcpyHtoD,0x{addr:016x},{sz}\n")
            kl.write("kernel-1.traceg\n")
        # minimal run.sh / stats.csv for completeness (unused by trace-driven)
        with open(os.path.join(appdir, "run.sh"), "w") as rs:
            rs.write("# synthesized LLM kernel trace (see gen_llm_traces.py)\n")
        with open(os.path.join(appdir, "traces", "stats.csv"), "w") as st:
            st.write("kernel id, kernel mangled name, grid_dimX, grid_dimY,"
                     " grid_dimZ, #blocks, block_dimX, block_dimY, block_dimZ,"
                     " #threads, total_insts, total_reported_insts\n")
            st.write(f"kernel-1.trace, _Z{name}, 1,1,1, 1, 1,1,1, 1, 0, 0\n")
        tot = sum(1 for _ in open(os.path.join(appdir, "traces", "kernel-1.traceg")))
        print(f"[gen] {name}: kernel-1.traceg {tot} lines")
    print(f"[gen] suite root: {suite}")


if __name__ == "__main__":
    main()
