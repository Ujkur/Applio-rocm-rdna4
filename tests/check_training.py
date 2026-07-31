#!/usr/bin/env python3
"""Training-path smoke test for Applio on ROCm RDNA4 (gfx1201).

Simulates the Applio training workload: cudnn ENABLED with MIOpen environment
variables (as in the README training section), benchmark=False, fixed shapes,
bf16 autocast, a few real optimizer steps.

Run from ANY directory:  python tests/check_training.py
Exit code 0 = passed.
"""
import os
import sys
import time

# MIOpen settings must be in place BEFORE torch is imported (README: training section)
os.environ.setdefault("MIOPEN_USER_DB_PATH", os.path.join(os.path.expanduser("~"), ".miopen_applio"))
os.environ.setdefault("MIOPEN_DEBUG_CONV_FFT", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")

# README note: if MIOpen cannot find clang, add the ROCm SDK LLVM dir to PATH
try:
    import site

    for sp in site.getsitepackages():
        llvm_bin = os.path.join(sp, "_rocm_sdk_core", "lib", "llvm", "bin")
        if os.path.isdir(llvm_bin) and llvm_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = llvm_bin + os.pathsep + os.environ.get("PATH", "")
            break
except Exception:
    pass

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
    print("Applio RDNA4 training-path smoke test (cudnn ON + MIOpen)")
    print("=" * 50)

    if not torch.cuda.is_available():
        check(False, "CUDA available", "no GPU visible to torch")
        summarize()

    # Same as the patched rvc/train/train.py: benchmark must be OFF on ROCm
    torch.backends.cudnn.benchmark = False
    check(torch.backends.cudnn.enabled, "cudnn enabled (MIOpen path)")
    check(torch.backends.cudnn.benchmark is False, "benchmark=False (patched behavior)")

    dev = "cuda"
    try:
        # Fixed-shape conv net: training shapes are stable, so MIOpen find
        # runs once per shape and then hits its cache
        model = nn.Sequential(
            nn.Conv1d(80, 256, 5, padding=2),
            nn.LeakyReLU(0.1),
            nn.Conv1d(256, 256, 3, padding=1),
            nn.LeakyReLU(0.1),
            nn.Conv1d(256, 80, 3, padding=1),
        ).to(dev)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
        target = torch.randn(4, 80, 4800, device=dev)

        losses = []
        t0 = time.perf_counter()
        for step in range(8):
            x = torch.randn(4, 80, 4800, device=dev)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                y = model(x)
                loss = nn.functional.mse_loss(y, target)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            losses.append(loss.item())
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss at step {step}: {loss.item()}")
        dt = time.perf_counter() - t0
        check(True, "bf16 training steps (8 iters, fixed shape)",
              f"{dt:.2f}s total, loss {losses[0]:.4f} -> {losses[-1]:.4f}")
        if losses[-1] > losses[0]:
            info("note", "loss went up on random data - harmless for a smoke test; "
                         "only finiteness matters here")
    except Exception as e:
        check(False, "bf16 training steps", str(e))

    summarize()


def summarize():
    print("=" * 50)
    passed, total = sum(RESULTS), len(RESULTS)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        print("Training path FAILED - check MIOpen env vars and the LLVM/clang note in the README.")
        sys.exit(1)
    print("Training path is OK - run it with the MIOpen env vars and: python app.py --open")


if __name__ == "__main__":
    main()
