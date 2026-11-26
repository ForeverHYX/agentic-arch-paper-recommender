#!/usr/bin/env python3
"""Second independent workload universe: synthetic Accel-Sim SASS traces (V100/SM7).

2026-11-26 second-universe round (pre-registered in
paper-ideas/experiments/20261126-second-universe/PRE_REGISTRATION.md).

Independence from the first universe (20261023/24 gen_llm_traces.py, archived in
paper-ideas/experiments/2026102{3,4}-*/gen_llm_traces.py):
  1. per-column RNG (seed base 26112601) drives address-phase jitter, tile
     visit order permutations, stride alternation -- the first universe was
     fully deterministic (no RNG);
  2. behavioral parameter centers/dispersions shifted: arithmetic intensity
     (448/12 and 320/24 FMA-per-load GEMMs vs 512/16; batch 64 vs 32 FMA/load),
     memory locality (KV slices 320/384KB vs 288KB; tile panel 5MB vs 4MB;
     stream 16MB vs 64MB), parallelism (112/80/36/320 CTAs vs 96/128/32/640;
     occupancy probe nregs 176 ILP=3 vs 200 ILP=2);
  3. pool size 12 info columns (vs 10), including latency-chain and mixed
     profiles the first-universe matrix never contained;
  4. junk columns H1-H8: same dependent-load-chain MECHANISM as J1-J8 (the
     only mechanism that yields zero-information columns in a universe with
     the half-core-clock config, see 20261024 RESULT §5.4) but new chain
     lengths / CTA counts / address regions / seeds -> a different tier-0
     junk set.

Trace-format rules inherited verbatim from the proven first-universe writer
(field-level alignment with trace_parser.cc @ dev; 2026-10-22 lessons:
MAX_DST=1, MAX_SRC=4; base_stride addressing mode; opcodes restricted to the
set already simulated green on QV100: EXIT/IMAD/IADD3/FFMA/FADD/MUFU.RCP/
MUFU.EX2/LDG.E.128/LDG.E.SYS/STG.E.SYS).

Usage: python3 gen2_traces.py <hw_run_root> [--selfcheck]
"""
import os
import sys

import numpy as np

MASK = "ffffffff"
# shifted device-pointer windows (+64GB) vs first universe
BASE_W = 0x00007F4000000000
BASE_ACT = 0x00007F5000000000
BASE_KV = 0x00007F6000000000
BASE_OUT = 0x00007F7000000000
SEED_BASE = 26112601


class TraceWriter:
    def __init__(self, path, name, kid, grid, block, shmem, nregs):
        self.f = open(path, "w", buffering=1 << 22)
        self.f.write(f"-kernel name = {name}\n")
        self.f.write(f"-kernel id = {kid}\n")
        self.f.write(f"-grid dim = ({grid[0]},{grid[1]},{grid[2]})\n")
        self.f.write(f"-block dim = ({block[0]},{block[1]},{block[2]})\n")
        self.f.write(f"-shmem = {shmem}\n")
        self.f.write(f"-nregs = {nregs}\n")
        self.f.write("-binary version = 70\n")
        self.f.write("-cuda stream id = 0\n\n")
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
    for i in range(n):
        if i % 2 == 0:
            e.op([out + (i % 3)], "IMAD", [255, 255, 255])
        else:
            e.op([out + ((i - 1) % 3)], "IADD3", [out + ((i - 1) % 3), 255, 255])


# ---------------------------------------------------------------- info columns
def gen_gemm_prefill(appdir, rng):
    """SM probe, AI shifted up ~16%: 12 loads per 448-FFMA run (was 16/512)."""
    ncta, nwarps = 112, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z18u2_gemm_prefillPfS_S_ii", 1, (ncta, 1, 1),
                    (128, 1, 1), 8192, 96)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            order = rng.permutation(12)                       # RNG: load order
            phase = int(rng.integers(0, 4)) * 128             # RNG: phase jitter
            cta_base = BASE_W + cta * 32768 + wp * 4096 + phase
            for k in range(12):
                e.mem("LDG.E.128", [16 + k], [4],
                      cta_base + int(order[k]) * 512, 16, 16)
            rot = int(rng.integers(0, 32))                    # RNG: operand rotation
            for it in range(8):
                for j in range(448):
                    acc = j % 8
                    a = 16 + ((j // 8 + rot) % 12)
                    b = 44 + ((j // 8 + rot) % 24)
                    e.op([acc], "FFMA", [acc, a, b])
                e.mem("LDG.E.128", [16], [4],
                      cta_base + 16384 + it * 512, 16, 16)
            for j in range(4):
                e.op([8 + j], "FADD", [2 * j, 2 * j + 1])
            for j in range(4):
                e.mem("STG.E.SYS", [], [8 + j // 2, 12],
                      BASE_OUT + cta * 4096 + wp * 1024 + j * 256, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_gemm_wide(appdir, rng):
    """SM probe, AI shifted down: 24 loads per 320-FFMA run (latency exposure)."""
    ncta, nwarps = 96, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z13u2_gemm_widePfS_S_i", 1, (ncta, 1, 1),
                    (128, 1, 1), 8192, 80)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            cta_base = BASE_W + cta * 36864 + wp * 4096 \
                + 256 * int(rng.integers(0, 3))
            for k in range(24):
                e.mem("LDG.E.128", [16 + k % 20], [4], cta_base + k * 512, 16, 16)
            for it in range(8):
                for j in range(320):
                    acc = j % 8
                    a = 16 + ((j // 8) % 20)
                    b = 48 + ((j // 8) % 16)
                    e.op([acc], "FFMA", [acc, a, b])
                if it % 2 == 0:
                    e.mem("LDG.E.128", [16], [4],
                          cta_base + 20480 + (it // 2) * 512, 16, 16)
            for j in range(4):
                e.op([8 + j], "FADD", [2 * j, 2 * j + 1])
                e.mem("STG.E.SYS", [], [8 + j, 12],
                      BASE_OUT + cta * 4096 + wp * 1024 + j * 256, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_attn_prefill(appdir, rng):
    """Mixed bound: 12 x 320KB = 3.84MB K/V window (was 16 x 256KB = 4MB)."""
    ncta, nwarps = 128, 4
    ntiles, tile_sz = 12, 327680
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z17u2_attn_prefillPfS_S_ii", 1, (ncta, 1, 1),
                    (128, 1, 1), 4096, 80)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            q = BASE_ACT + cta * 1024 + wp * 256 + int(rng.integers(0, 2)) * 128
            for k in range(4):
                e.mem("LDG.E.128", [16 + k], [4], q + k * 512, 16, 16)
            perm = rng.permutation(ntiles)                    # RNG: tile order
            for it in range(36):
                tile = int(perm[it % ntiles])
                kv = BASE_KV + tile * tile_sz + wp * 8192 + (it % 64) * 512
                e.mem("LDG.E.128", [32], [4], kv, 16, 16)
                e.mem("LDG.E.128", [36], [4], kv + tile_sz // 2, 16, 16)
                for j in range(12):
                    e.op([j % 8], "FFMA", [j % 8, 16 + (j % 16), 32 + (j % 4)])
                e.op([10], "MUFU.RCP", [0])
                e.op([11], "MUFU.EX2", [10])
                e.op([12], "FADD", [11, 255])
                for j in range(8):
                    e.op([j], "FFMA", [j, 36 + (j % 4), 11])
            e.mem("STG.E.SYS", [], [0, 12], BASE_OUT + cta * 512 + wp * 128, 4, 4)
            e.mem("STG.E.SYS", [], [1, 12], BASE_OUT + cta * 512 + wp * 128 + 4, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def _kv_scan(appdir, rng, groups, slice_sz, ncta, iters, mangle, nregs,
             fma_per_load=2, rows=1):
    nwarps = 4
    wp_per_grp = ncta * nwarps // groups
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    mangle, 1, (ncta, 1, 1), (128, 1, 1), 2048, nregs)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            grp = (cta * nwarps + wp) // wp_per_grp
            lane = (cta * nwarps + wp) % wp_per_grp
            phase = int(rng.integers(0, 8))                   # RNG: scan phase
            sl = BASE_KV + grp * slice_sz
            for it in range(iters):
                off = ((it * wp_per_grp + lane + phase) * 512) % (slice_sz - 512)
                e.mem("LDG.E.128", [16], [4], sl + off, 16, 16)
                if rows == 1:
                    for f in range(fma_per_load):
                        e.op([0], "FFMA", [0, 16 + 2 * f, 17 + 2 * f])
                else:
                    for r in range(rows):
                        for f in range(fma_per_load // rows):
                            e.op([r], "FFMA", [r, 16 + (f % 8), 17])
            for r in range(max(2, rows)):
                if r < 2:
                    e.op([8 + r], "FADD", [0 if r == 0 else 1, 255])
            e.op([9], "MUFU.EX2", [8])
            e.op([2], "FFMA", [1, 9, 8])
            e.mem("STG.E.SYS", [], [2, 12], BASE_OUT + grp * 512 + lane * 64, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_kv_mid(appdir, rng):
    """L2-capacity probe: 12 x 320KB = 3.84MB live (3MB thrashes, 6MB holds)."""
    _kv_scan(appdir, rng, 12, 320 * 1024, 36, 72,
             "_Z11u2_kv_midPfS_S_i", 64)


def gen_kv_small(appdir, rng):
    """Weak control: 6 x 320KB = 1.92MB (fits both L2 sizes)."""
    _kv_scan(appdir, rng, 6, 320 * 1024, 24, 64,
             "_Z13u2_kv_smallPfS_S_i", 64)


def gen_kv_big(appdir, rng):
    """Weak control: 28 x 384KB = 10.75MB (thrashes both L2 sizes)."""
    _kv_scan(appdir, rng, 28, 384 * 1024, 28, 64,
             "_Z12u2_kv_bigPfS_S_i", 64)


def gen_batch_dec(appdir, rng):
    """Compute-hiding batch-16 decode: 64 FMA per KV load (was 32)."""
    _kv_scan(appdir, rng, 12, 320 * 1024, 120, 48,
             "_Z13u2_batch_decPfS_S_i", 64, fma_per_load=64, rows=8)


def gen_stream(appdir, rng):
    """Streaming control: 16MB unique (was 64MB); latency/issue bound."""
    ncta, nwarps = 16, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z12u2_streamPfS_i", 1, (ncta, 1, 1), (128, 1, 1), 1024, 64)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            wid = cta * nwarps + wp                          # 64 warps x 256KB
            base = BASE_W + int(rng.integers(0, 2)) * 512 + wid * 262144
            for it in range(512):
                e.mem("LDG.E.128", [16], [4], base + it * 512, 16, 16)
                e.op([0], "FFMA", [0, 16, 17])
                if it % 64 == 63:
                    e.op([1], "FADD", [0, 1])
            e.mem("STG.E.SYS", [], [0, 12], BASE_OUT + wid * 16, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_elem(appdir, rng):
    """Elementwise control: streaming, low AI."""
    ncta, nwarps = 96, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z10u2_elemPfS_i", 1, (ncta, 1, 1), (128, 1, 1), 512, 48)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            base = BASE_ACT + (cta * nwarps + wp) * 16384 \
                + int(rng.integers(0, 4)) * 256
            for it in range(48):
                a = base + it * 256 + (256 if rng.integers(0, 3) == 0 else 0)
                e.mem("LDG.E.SYS", [16], [4], a, 4, 4)
                e.op([0], "FADD", [16, 16])
                e.op([1], "MUFU.EX2", [0])
                e.op([2], "FADD", [1, 255])
                e.mem("STG.E.SYS", [], [2, 12], a + 4194304, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_occu(appdir, rng):
    """RF-occupancy probe: nregs=176 -> 65536/22528=2 CTAs/SM, RFh -> 1."""
    ncta, nwarps = 512, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z11u2_occuPfS_S_i", 1, (ncta, 1, 1),
                    (128, 1, 1), 4096, 176)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            cta_base = BASE_W + cta * 20480 + wp * 4096 \
                + int(rng.integers(0, 4)) * 512
            for k in range(6):                                # 3KB fragments
                e.mem("LDG.E.128", [16 + k], [4], cta_base + k * 512, 16, 16)
            for it in range(12):                              # ILP=3 chains
                for j in range(128):
                    acc = j % 3
                    a = 16 + ((j // 3) % 6)
                    b = 24 + ((j // 3) % 4)
                    e.op([acc], "FFMA", [acc, a, b])
                if it % 3 == 0:
                    e.mem("LDG.E.128", [16], [4],
                          cta_base + 16384 + (it // 3) * 512, 16, 16)
            for j in range(3):
                e.op([8 + j], "FADD", [j, 255])
                e.mem("STG.E.SYS", [], [8 + j, 12],
                      BASE_OUT + cta * 768 + wp * 192 + j * 64, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_lat_chain(appdir, rng):
    """Issue/latency column (ILP=1), RF-free (nregs=32); new to the matrix."""
    ncta, nwarps = 320, 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z14u2_lat_chainPf_i", 1, (ncta, 1, 1), (128, 1, 1), 1024, 32)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            e.mem("LDG.E.SYS", [16], [4],
                  BASE_ACT + (cta * nwarps + wp) * 256
                  + int(rng.integers(0, 2)) * 128, 4, 4)
            e.op([0], "FFMA", [0, 16, 17])
            for j in range(768):
                e.op([0], "FFMA", [0, 0, 16])
            e.mem("STG.E.SYS", [], [0, 12],
                  BASE_OUT + (cta * nwarps + wp) * 16, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


def gen_tile(appdir, rng):
    """SM+L2: shared 5MB B-panel (20 x 256KB, cycled 3x; 6MB holds, 3MB thrashes)."""
    ncta, nwarps = 80, 4
    panel, block = 5 * 1024 * 1024, 256 * 1024
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    "_Z11u2_tilePfS_S_i", 1, (ncta, 1, 1), (128, 1, 1), 8192, 64)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            wg = cta * nwarps + wp                            # 320 global warps
            e.mem("LDG.E.128", [20], [4], BASE_ACT + wg * 1024, 16, 16)
            perm = rng.permutation(panel // block)            # RNG: block order
            for it in range(60):
                blk = int(perm[it % (panel // block)]) * block
                b = BASE_W + blk + (wg % (block // 1024)) * 1024
                e.mem("LDG.E.128", [16], [4], b, 16, 16)
                e.mem("LDG.E.128", [17], [4], b + 512, 16, 16)
                for j in range(24):
                    e.op([j % 4], "FFMA", [j % 4, 16 + (j % 2), 20])
            for j in range(4):
                e.mem("STG.E.SYS", [], [j, 12],
                      BASE_OUT + wg * 256 + j * 64, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


# ---------------------------------------------------------------- junk columns
# Same MECHANISM as first-universe J1-J8 (dependent-load chains, MLP=1, unique
# streaming, <=16 CTAs, low nregs -> flat on SM/L2/RF; time set by non-core
# clock domains) with NEW chain lengths / address regions / seeds.
JUNK_SPECS = [          # (name, L, ncta, fill_ffma_per_step, nregs, seed_off)
    ("u2-junk-h1", 46, 16, 0, 24, 0),
    ("u2-junk-h2", 22,  8, 2, 32, 1),
    ("u2-junk-h3", 34, 16, 0, 24, 2),
    ("u2-junk-h4", 18, 16, 1, 40, 3),
    ("u2-junk-h5", 42,  8, 2, 32, 4),
    ("u2-junk-h6", 26,  8, 0, 24, 5),
    ("u2-junk-h7", 38, 16, 1, 40, 6),
    ("u2-junk-h8", 30, 16, 0, 24, 7),
]


def gen_junk_chain(appdir, rng, L, ncta, fill, nregs, seed_off):
    nwarps = 4
    w = TraceWriter(os.path.join(appdir, "traces", "kernel-1.traceg"),
                    f"_Z11u2_junk_h{seed_off + 1}Pf_i", 1, (ncta, 1, 1),
                    (128, 1, 1), 512, nregs)
    for cta in range(ncta):
        w.begin_tb((cta, 0, 0))
        for wp in range(nwarps):
            e = Emitter()
            addr_math(e)
            wid = cta * nwarps + wp
            base = BASE_W + (wid + seed_off * 64) * 262144 \
                + int(rng.integers(0, 8)) * 512
            e.mem("LDG.E.128", [16], [4], base, 16, 16)
            for it in range(L):
                e.mem("LDG.E.128", [16], [16], base + (it + 1) * 512, 16, 16)
                for f in range(fill):
                    e.op([8 + f % 2], "FFMA", [8 + f % 2, 20, 21])
            e.op([8], "FADD", [8, 16])
            e.mem("STG.E.SYS", [], [8, 12], BASE_OUT + wid * 16 + seed_off * 4, 4, 4)
            e.exit()
            w.warp(wp, e.lines)
        w.end_tb()
    w.close()


APPS = [
    ("u2-gemm-prefill", gen_gemm_prefill, [
        ("MemcpyHtoD", BASE_W, 33554432), ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("u2-gemm-wide", gen_gemm_wide, [
        ("MemcpyHtoD", BASE_W, 33554432), ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("u2-attn-prefill", gen_attn_prefill, [
        ("MemcpyHtoD", BASE_KV, 4194304), ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("u2-kv-mid", gen_kv_mid, [
        ("MemcpyHtoD", BASE_KV, 3932160), ("MemcpyHtoD", BASE_ACT, 65536)]),
    ("u2-kv-small", gen_kv_small, [
        ("MemcpyHtoD", BASE_KV, 1966080), ("MemcpyHtoD", BASE_ACT, 65536)]),
    ("u2-kv-big", gen_kv_big, [
        ("MemcpyHtoD", BASE_KV, 11010048), ("MemcpyHtoD", BASE_ACT, 65536)]),
    ("u2-batch-dec", gen_batch_dec, [
        ("MemcpyHtoD", BASE_KV, 3932160), ("MemcpyHtoD", BASE_ACT, 65536)]),
    ("u2-stream", gen_stream, [
        ("MemcpyHtoD", BASE_W, 16777216), ("MemcpyHtoD", BASE_ACT, 16384)]),
    ("u2-elem", gen_elem, [
        ("MemcpyHtoD", BASE_ACT, 8388608)]),
    ("u2-occu", gen_occu, [
        ("MemcpyHtoD", BASE_W, 16777216)]),
    ("u2-lat-chain", gen_lat_chain, [
        ("MemcpyHtoD", BASE_ACT, 1048576)]),
    ("u2-tile", gen_tile, [
        ("MemcpyHtoD", BASE_W, 5242880), ("MemcpyHtoD", BASE_ACT, 1048576)]),
]
JUNK_APPS = [
    (name, (lambda d, r, s=spec: gen_junk_chain(d, r, *s)),
     [("MemcpyHtoD", BASE_W, 8388608)])
    for (name, *spec) in JUNK_SPECS
]
APPS = APPS + JUNK_APPS


def main():
    selfcheck = "--selfcheck" in sys.argv
    root = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
        else "hw_run"
    suite = os.path.join(root, "llm-synth", "9.1")
    for i, (name, fn, copies) in enumerate(APPS):
        appdir = os.path.join(suite, name, "all")
        os.makedirs(os.path.join(appdir, "traces"), exist_ok=True)
        rng = np.random.default_rng(SEED_BASE + i)           # per-column seed
        fn(appdir, rng)
        with open(os.path.join(appdir, "traces", "kernelslist.g"), "w") as kl:
            for _, addr, sz in copies:
                kl.write(f"MemcpyHtoD,0x{addr:016x},{sz}\n")
            kl.write("kernel-1.traceg\n")
        with open(os.path.join(appdir, "run.sh"), "w") as rs:
            rs.write("# second-universe synthesized LLM kernel trace\n")
        with open(os.path.join(appdir, "traces", "stats.csv"), "w") as st:
            st.write("kernel id, kernel mangled name, grid_dimX, grid_dimY,"
                     " grid_dimZ, #blocks, block_dimX, block_dimY, block_dimZ,"
                     " #threads, total_insts, total_reported_insts\n")
            st.write(f"kernel-1.trace, _Z{name}, 1,1,1, 1, 1,1,1, 1, 0, 0\n")
        path = os.path.join(appdir, "traces", "kernel-1.traceg")
        tot = sum(1 for _ in open(path))
        print(f"[gen] {name}: kernel-1.traceg {tot} lines")
        if selfcheck:
            selfcheck_file(path)
    print(f"[gen] suite root: {suite}")


WHITE = {"EXIT", "IMAD", "IADD3", "FFMA", "FADD", "MUFU.RCP", "MUFU.EX2",
         "LDG.E.128", "LDG.E.SYS", "STG.E.SYS"}


def selfcheck_file(path):
    """Field-level invariants: MAX_DST=1, MAX_SRC=4, opcode whitelist, format."""
    n = 0
    with open(path) as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith(("#", "thread block", "warp =", "insts =")):
                continue
            parts = s.split()
            if len(parts) < 9 or not parts[0].isdigit():
                continue
            dn = int(parts[6])
            dests = parts[7:7 + dn]
            opcode = parts[7 + dn]
            sn = int(parts[8 + dn])
            srcs = parts[9 + dn:9 + dn + sn]
            assert opcode in WHITE, f"{path}: opcode {opcode} not whitelisted"
            assert dn <= 1, f"{path}: dest_num {dn} > MAX_DST=1"
            assert sn <= 4, f"{path}: src_num {sn} > MAX_SRC=4"
            for r in dests + srcs:
                assert r.startswith("R") and 0 <= int(r[1:]) < 256, f"{path}: {r}"
            n += 1
    print(f"[chk] {os.path.basename(os.path.dirname(os.path.dirname(path)))}:"
          f" {n} inst lines OK (dst<=1, src<=4, opcode whitelist)", flush=True)


if __name__ == "__main__":
    main()
