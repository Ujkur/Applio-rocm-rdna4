#!/usr/bin/env python3
"""Environment check for Applio on ROCm RDNA4 (gfx1201).

Verifies Python version, ROCm torch, GPU visibility and bf16 compute.
Run from ANY directory:  python tests/check_environment.py
Exit code 0 = all checks passed.
"""
import sys

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
    print("Applio RDNA4 environment check")
    print("=" * 50)

    # 1. Python 3.12
    v = sys.version_info
    check(v.major == 3 and v.minor == 12, "Python 3.12", f"found {v.major}.{v.minor}.{v.micro}")

    # 2. torch present and ROCm build
    try:
        import torch
    except Exception as e:
        check(False, "import torch", str(e))
        return summarize()
    check("rocm" in torch.__version__.lower(), "torch is a ROCm build", torch.__version__)

    # 3. GPU visible
    check(torch.cuda.is_available(), "torch.cuda.is_available()")
    if not torch.cuda.is_available():
        return summarize()
    info("GPU", torch.cuda.get_device_name(0))

    # 4. bf16 supported and numerically sane
    check(torch.cuda.is_bf16_supported(), "bf16 supported")
    try:
        a = torch.randn(512, 512, device="cuda", dtype=torch.bfloat16)
        b = torch.randn(512, 512, device="cuda", dtype=torch.bfloat16)
        out = (a @ b).float()
        ref = a.float() @ b.float()
        rel = ((out - ref).abs().max() / ref.abs().max().clamp_min(1e-6)).item()
        ok = bool(torch.isfinite(out).all()) and rel < 0.05
        check(ok, "bf16 matmul on GPU", f"max rel error {rel:.4%}")
    except Exception as e:
        check(False, "bf16 matmul on GPU", str(e))

    # 5. torch.distributed status (expected: unavailable on ROCm Windows builds)
    import torch.distributed as dist
    dist_ok = dist.is_available() and hasattr(dist, "init_process_group")
    if dist_ok:
        info("torch.distributed", "available (multi-GPU possible)")
    else:
        info("torch.distributed", "not available - normal on ROCm Windows; "
                                  "the train.py patch already guards this (single-GPU unaffected)")

    summarize()


def summarize():
    print("=" * 50)
    passed, total = sum(RESULTS), len(RESULTS)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        print("Some checks FAILED - see README installation steps.")
        sys.exit(1)
    print("Environment is ready.")


if __name__ == "__main__":
    main()
