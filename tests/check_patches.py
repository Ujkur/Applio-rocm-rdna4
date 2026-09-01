#!/usr/bin/env python3
"""Patch verification for Applio on ROCm RDNA4 (gfx1201).

Verifies that all RDNA4 patches are applied in an Applio installation,
that the patched files still compile, and that the faiss CJK-path
workaround actually works.

Run from the Applio root:        python <guide-repo>/tests/check_patches.py
Or pass the Applio path:         python tests/check_patches.py C:/path/to/Applio
Exit code 0 = all checks passed.
"""
import json
import os
import py_compile
import shutil
import sys
import tempfile

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


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    print("Applio RDNA4 patch verification")
    print("=" * 50)
    info("Applio root", root)

    if not (os.path.isfile(os.path.join(root, "app.py")) and os.path.isdir(os.path.join(root, "rvc"))):
        print("ERROR: not an Applio root (app.py / rvc/ not found). "
              "Run from the Applio directory or pass its path as an argument.")
        sys.exit(2)

    # 1. config.py chunk parameters
    p = os.path.join(root, "rvc", "configs", "config.py")
    c = read(p)
    check("(1, 3, 5, 6)" in c, "config.py chunk params (1,3,5,6)")

    # 2. pipeline.py: crossfade + faiss CJK + imports
    p = os.path.join(root, "rvc", "infer", "pipeline.py")
    c = read(p)
    check("fade_len" in c, "pipeline.py equal-power crossfade")
    check("mkdtemp" in c, "pipeline.py faiss CJK-path workaround")
    check("import tempfile" in c, "pipeline.py tempfile/shutil imports")

    # 3. train.py: benchmark=False + distributed guard
    p = os.path.join(root, "rvc", "train", "train.py")
    c = read(p)
    check("torch.backends.cudnn.benchmark = False" in c, "train.py benchmark=False")
    check('hasattr(dist, "init_process_group")' in c or "dist.is_available()" in c,
          "train.py distributed guard")

    # 4. config_template.json precision
    p = os.path.join(root, "assets", "config_template.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            precision = json.load(f).get("precision")
        check(precision == "bf16", "config_template.json precision=bf16", f"found {precision!r}")
    except Exception as e:
        check(False, "config_template.json precision=bf16", str(e))

    # 4b. prerequisites_download.py: url_base -> hf-mirror.com (国内镜像)
    p = os.path.join(root, "rvc", "lib", "tools", "prerequisites_download.py")
    try:
        c = read(p)
        check("hf-mirror.com" in c, "prerequisites_download.py url_base hf-mirror")
    except Exception as e:
        check(False, "prerequisites_download.py url_base hf-mirror", str(e))

    # 5. cudnn-off inference entry
    check(os.path.isfile(os.path.join(root, "applio_cudnn_off.py")),
          "applio_cudnn_off.py present")

    # 6. Patched files still compile
    for rel in ("rvc/configs/config.py", "rvc/infer/pipeline.py", "rvc/train/train.py"):
        path = os.path.join(root, rel)
        try:
            py_compile.compile(path, doraise=True)
            check(True, f"compiles: {rel}")
        except py_compile.PyCompileError as e:
            check(False, f"compiles: {rel}", str(e).splitlines()[0])

    # 7. Functional test: faiss CJK path (the reason for patch #3)
    check_faiss_cjk()

    summarize()


def check_faiss_cjk():
    try:
        import faiss
        import numpy as np
    except ImportError:
        info("faiss CJK functional test", "faiss/numpy not installed, skipped")
        return

    idx = faiss.IndexFlatL2(4)
    idx.add(np.random.rand(8, 4).astype("float32"))

    # faiss cannot write to CJK paths either (same C fopen limitation),
    # so write to an ASCII path first and copy with shutil (CJK-safe)
    ascii_seed = os.path.join(tempfile.mkdtemp(prefix="faiss_seed_"), "index")
    faiss.write_index(idx, ascii_seed)

    cjk_dir = os.path.join(tempfile.gettempdir(), "applio_中文路径测试")
    os.makedirs(cjk_dir, exist_ok=True)
    cjk_path = os.path.join(cjk_dir, "索引.index")
    shutil.copy2(ascii_seed, cjk_path)

    # Direct read from a CJK path: fails on Windows with faiss builds that use C fopen
    try:
        faiss.read_index(cjk_path)
        info("faiss direct CJK read", "works on this faiss build (patch not strictly needed, harmless)")
        direct_ok = True
    except Exception:
        direct_ok = False
        info("faiss direct CJK read", "fails as expected on Windows (C fopen) - patch is required")

    # The workaround used by the patched pipeline.py must always succeed
    try:
        tmp_dir = tempfile.mkdtemp(prefix="faiss_")
        ascii_path = os.path.join(tmp_dir, "index")
        shutil.copy2(cjk_path, ascii_path)
        loaded = faiss.read_index(ascii_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        check(loaded.ntotal == 8, "faiss ASCII-temp workaround", f"ntotal={loaded.ntotal}")
    except Exception as e:
        check(False, "faiss ASCII-temp workaround", str(e))

    shutil.rmtree(cjk_dir, ignore_errors=True)
    shutil.rmtree(os.path.dirname(ascii_seed), ignore_errors=True)
    if not direct_ok:
        info("note", "without the patch, inference would crash on CJK paths like the test above")


def summarize():
    print("=" * 50)
    passed, total = sum(RESULTS), len(RESULTS)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        print("Some patches are MISSING - re-run: python apply_rdna4_patches.py")
        sys.exit(1)
    print("All RDNA4 patches are correctly applied.")


if __name__ == "__main__":
    main()
