#!/usr/bin/env python3
"""Inference-path smoke test for Applio on ROCm RDNA4 (gfx1201).

Simulates the Applio inference workload: cudnn DISABLED (as applio_cudnn_off.py
does), varying convolution shapes (audio chunks of varying length), bf16.
On gfx1201, cudnn/MIOpen find crashes on varying shapes - that is why inference
must run with cudnn off. This test verifies the bypassed path works.

Run from ANY directory:  python tests/check_inference.py
Exit code 0 = passed.
"""
import sys
import time

import torch
import torch.nn as nn

RESULTS = []


def check(ok, name, detail=""):
    RESULTS.append(bool(ok))
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}"
    if detail:
        line += f" -- {detail}"
    print(line)


def info(name, detail):
    print(f"[INFO] {name} -- {detail}")


def main():
    print("Applio RDNA4 inference-path smoke test (cudnn OFF)")
    print("=" * 50)

    if not torch.cuda.is_available():
        check(False, "CUDA available", "no GPU visible to torch")
        summarize()

    # Same as applio_cudnn_off.py does before launching app.py
    torch.backends.cudnn.enabled = False
    check(torch.backends.cudnn.enabled is False, "cudnn disabled (MIOpen bypassed)")

    dev = "cuda"
    try:
        # A small conv stack resembling an RVC/HiFi-GAN-style frontend
        model = nn.Sequential(
            nn.Conv1d(80, 192, 5, padding=2),
            nn.LeakyReLU(0.1),
            nn.Conv1d(192, 192, 3, padding=1),
            nn.LeakyReLU(0.1),
            nn.Conv1d(192, 80, 3, padding=1),
        ).to(dev)

        # Varying lengths simulate chunk-by-chunk inference (this is what
        # crashes MIOpen find when cudnn is enabled on gfx1201)
        lengths = [24000, 96000, 48000, 192000, 36000, 144000, 72000, 120000]
        t0 = time.perf_counter()
        with torch.no_grad():
            for n, length in enumerate(lengths, 1):
                x = torch.randn(1, 80, length, device=dev)
                y = model(x)
                assert y.shape == x.shape, f"shape mismatch {y.shape} vs {x.shape}"
                assert torch.isfinite(y).all(), f"non-finite output at iteration {n}"
        dt = time.perf_counter() - t0
        check(True, "fp32 conv, varying shapes (8 chunks)", f"{dt:.2f}s total")
    except Exception as e:
        check(False, "fp32 conv, varying shapes", str(e))
        summarize()

    try:
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            for length in (48000, 144000):
                x = torch.randn(1, 80, length, device=dev)
                y = model(x)
                assert torch.isfinite(y).all(), "non-finite bf16 output"
        check(True, "bf16 autocast conv")
    except Exception as e:
        check(False, "bf16 autocast conv", str(e))

    summarize()


def summarize():
    print("=" * 50)
    passed, total = sum(RESULTS), len(RESULTS)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        print("Inference path FAILED - do NOT run app.py for inference; "
              "use: python applio_cudnn_off.py --open")
        sys.exit(1)
    print("Inference path is OK - run it with: python applio_cudnn_off.py --open")


if __name__ == "__main__":
    main()
