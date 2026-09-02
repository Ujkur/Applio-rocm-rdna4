<div align="center">

# Applio ROCm RDNA4

**Run [Applio](https://github.com/IAHispano/Applio) training and inference on AMD RX 9000 series GPUs (gfx1201 / RDNA4)**

[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![GPU](https://img.shields.io/badge/GPU-RX%209000%20Series%20%28gfx1201%29-ED1C24)
![ROCm](https://img.shields.io/badge/ROCm-7.2.1-0066CC)
![PyTorch](https://img.shields.io/badge/PyTorch-2.9.1%2Brocm7.2.1-EE4C2C)

[中文](README.md) · [English](README_EN.md)

</div>

The original Applio has **5 issues** on RDNA4 GPUs: inference crashes, metallic artifacts on long audio, CJK path errors, training errors, and slow training. This repo provides a **one-click patch script** that fixes all of them, plus **1 stitching quality optimization**. Code changes only — no model weights involved.

## Issues and Fixes

| # | Issue | Severity | Fix | Modified File |
|---|-------|----------|-----|---------------|
| 1 | MIOpen crash during inference | Critical | Disable cudnn, use ATen native convolution (actually faster) | `applio_cudnn_off.py` (new) |
| 2 | Metallic artifacts on long audio | Critical | `x_center=5`, each NSF forward ≈7s (threshold 7-8s) | `rvc/configs/config.py` |
| 3 | faiss doesn't support CJK paths | Medium | Auto-copy non-ASCII paths to a temp dir before loading | `rvc/infer/pipeline.py` |
| 4 | Training `init_process_group` error | Critical | `hasattr` check, skip for single GPU | `rvc/train/train.py` |
| 5 | Slow training | Medium | `benchmark=False` to avoid repeated MIOpen find | `rvc/train/train.py` |
| 6 | Prerequisite download times out on first launch (China network) | Critical | prerequisites download source switched to hf-mirror.com | `rvc/lib/tools/prerequisites_download.py` |

> [!NOTE]
> Also includes a quality optimization: equal-power sin/cos crossfade (4096 samples / 85ms) replaces the bare `np.concatenate`, for smoother chunk stitching.

## Installation Methods

> Pick one of the two: **Method 1** is a manual step-by-step install (for advanced users who want full control); **Method 2** is a double-click one-click installer that performs exactly the same operations — Python / ROCm / PyTorch / Applio / patches / launchers, no command line needed.

### Method 1: Manual install (advanced)

#### Step 1 · Install Python 3.12

Download and install [Python 3.12](https://www.python.org/downloads/release/python-3120/) (check **Add to PATH**), then verify:

```cmd
python --version
```

Confirm the output shows `Python 3.12.x`.

#### Step 2 · Install ROCm SDK + PyTorch

> [!IMPORTANT]
> Requires AMD graphics driver **26.2.2 or newer** ([download from AMD](https://www.amd.com/en/support)).

Install the ROCm SDK:

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm-7.2.1.tar.gz
```

Install PyTorch (ROCm build, large download — may take several minutes):

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1+rocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1+rocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1+rocm7.2.1-cp312-cp312-win_amd64.whl
```

Verify GPU detection:

```cmd
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Expected output similar to:

```text
2.9.1+rocm7.2.1 True AMD Radeon RX 9070 XT
```

#### Step 3 · Download the original Applio

```cmd
git clone -b 3.6.4 --depth 1 https://github.com/IAHispano/Applio.git
cd Applio
```

> [!NOTE]
> The patch script matches the **3.6.4** source code exactly, so pin the version with `-b 3.6.4`. The upstream repo has been renamed to `IAHispano/Applio` (the old name `Applio-RVC-Fork` redirects). Other versions may cause patch misses — the script will warn explicitly instead of failing silently.

#### Step 4 · Install dependencies (skip torch)

> [!WARNING]
> Applio's `requirements.txt` pins `torch==2.11.0`. Installing it directly will **overwrite the ROCm torch from Step 2** — it must be filtered out.

Filter out torch-related lines, then install:

```cmd
findstr /v /b "torch==" requirements.txt | findstr /v /b "torchaudio==" | findstr /v /b "torchvision==" > requirements_no_torch.txt
pip install -r requirements_no_torch.txt
```

Or manually: open `requirements.txt` in Notepad, delete lines starting with `torch==`, `torchaudio==`, `torchvision==`, save, then `pip install -r requirements.txt`.

#### Step 5 · Download pretrained models

Applio requires pretrained models (HiFi-GAN vocoder, etc.). Two options:

1. **WebUI download (recommended)**: launch Applio (`python app.py --open`), then download pretrained models in the WebUI under "Settings" → "Training".
2. **Manual download**: download from the [official docs](https://docs.applio.org/getting-started/pretrained/) and place them in `rvc/models/pretraineds/`.

> [!CAUTION]
> **Do not run the official `run-install.bat`**. It creates a Conda environment and installs a non-ROCm torch, **breaking the ROCm torch environment set up in Step 2**. This guide completely bypasses the official install script.

#### Step 6 · Apply RDNA4 patches

Copy the two files from this repo into the Applio directory, then run the patch script:

```cmd
git clone https://github.com/Ujkur/Applio-rocm-rdna4.git
copy Applio-rocm-rdna4\applio_cudnn_off.py .
copy Applio-rocm-rdna4\apply_rdna4_patches.py .

python apply_rdna4_patches.py
```

The script automatically modifies 4 files (backing up originals as `.bak`) and confirms `applio_cudnn_off.py` is in place. Seeing `完成!` (Done) means success; if any pattern misses (usually a wrong Applio version), the script lists the problem and exits with a non-zero code. The script is idempotent — already-applied patches are skipped on re-run.

### Method 2: One-click install (recommended)

> Double-click a single script and everything installs automatically — no command line needed. Supports resume: if interrupted, just run it again; finished steps are skipped automatically.

**Requirements**: Windows 10/11 64-bit · AMD RX 9000 series GPU · [driver ≥ 26.2.2](https://www.amd.com/en/support) · ~20 GB disk · internet (first run downloads ~3 GB, ~10 GB installed)

1. Click the green **Code** button → **Download ZIP**, extract anywhere (or `git clone` this repo)
2. Double-click **install.bat** in the extracted folder
   - If "Windows protected your PC" appears: click "More info" → "Run anyway"
   - Fully automatic, ~20–60 minutes depending on network speed
3. Two desktop shortcuts appear — **do not mix them up**:

| Shortcut | Use | Internals |
|---|---|---|
| **Applio 推理 (Inference)** | voice conversion | `applio_cudnn_off.py`, cudnn off |
| **Applio 训练 (Training)** | model training | `app.py`, cudnn on + MIOpen env auto-set |

The installer puts Python 3.12, ROCm 7.2.1, PyTorch 2.9.1+rocm, Applio 3.6.4, all dependencies and the RDNA4 patches into one self-contained folder (default `C:\Applio-RDNA4`). **No system Python changes, no PATH writes, no registry, no admin rights** — delete the folder to fully uninstall. On success the download cache folder (`C:\Applio-RDNA4-cache`) is automatically deleted, freeing ~2.5 GB.

- Custom location: `install.bat D:\Applio-RDNA4`
- Uninstall: double-click `uninstall.bat`
- Interrupted install: just run `install.bat` again (downloads resume)
- Pretrained models: the patch points the prerequisites download source at hf-mirror.com (China mirror); they are downloaded automatically on first launch (~1 GB, incl. rmvpe/ContentVec/ffmpeg/HiFi-GAN). If it still fails, a VPN is needed.

## Verifying the Installation

This repo ships 4 test scripts to confirm the environment, the patches, and the inference/training paths all work. All `[PASS]` (exit code 0) means success:

| Script | What it verifies | Where to run |
|--------|------------------|--------------|
| `tests/check_environment.py` | Python 3.12, ROCm torch, GPU detection, bf16 compute | Any directory |
| `tests/check_patches.py` | All 6 patches in place, patched files compile, live faiss CJK-path test | Applio root (or pass the path as an argument) |
| `tests/check_inference.py` | Inference path: cudnn-off + varying-shape convs + bf16 | Any directory |
| `tests/check_training.py` | Training path: cudnn-on + MIOpen + real bf16 training steps | Any directory |

Run from the Applio root (assuming this repo was cloned into the `Applio-rocm-rdna4\` subdirectory per Step 6 of Method 1):

```cmd
python Applio-rocm-rdna4\tests\check_environment.py
python Applio-rocm-rdna4\tests\check_patches.py .
python Applio-rocm-rdna4\tests\check_inference.py
python Applio-rocm-rdna4\tests\check_training.py
```

> [!TIP]
> `check_training.py` sets the MIOpen environment variables and detects the LLVM path automatically — no manual `set` needed. Without an argument, `check_patches.py` checks the current directory.

## Usage

| Scenario | Launch command | cudnn | Why |
|----------|---------------|-------|-----|
| **Inference** | `python applio_cudnn_off.py --open` | Off | Convolution shapes vary; MIOpen find crashes every time |
| **Training** | `python app.py --open` | On | Shapes are fixed; MIOpen find caches after the first run, faster than native convolution |

Set the MIOpen environment variables before training:

```cmd
set MIOPEN_USER_DB_PATH=%USERPROFILE%\.miopen_applio
set MIOPEN_DEBUG_CONV_FFT=0
set MIOPEN_FIND_MODE=FAST
python app.py --open
```

If MIOpen reports clang not found during training, also set the LLVM path:

```cmd
set "PATH=<Python_install_path>\Lib\site-packages\_rocm_sdk_core\lib\llvm\bin;%PATH%"
```

> [!WARNING]
> **Do not mix the two entry points**: training with cudnn-off is slow; inference with cudnn-on crashes.

## Modification Details

### 1. `applio_cudnn_off.py` (new)

Inference entry script that executes `torch.backends.cudnn.enabled = False` before `app.py` starts.

### 2. `rvc/configs/config.py`

```diff
- x_pad, x_query, x_center, x_max = (1, 6, 38, 41)   # original: 38s per chunk, metallic artifacts
+ x_pad, x_query, x_center, x_max = (1, 3, 5, 6)     # RDNA4: ~5s per chunk, safe
```

`x_center` determines the chunk size (split step). Actual NSF forward length ≈ `x_center + 2s` (padding). The critical threshold is 7-8s; beyond that the latter part develops metallic artifacts. `x_center=5` gives an actual 7s, safe. `config.py` contains this parameter in two places (the default tier and the low-VRAM tier `(1, 5, 30, 32)`); the script replaces both.

### 3. `rvc/infer/pipeline.py`

- **crossfade (optimization)**: bare `np.concatenate` → equal-power sin/cos crossfade (4096 samples / 85ms), improves chunk stitching quality
- **faiss CJK path**: `faiss.read_index` uses C `fopen`, which doesn't support CJK/full-width paths. Non-ASCII paths are auto-copied to a temp directory before loading
- Added `import tempfile, shutil`

### 4. `rvc/train/train.py`

```diff
- torch.backends.cudnn.benchmark = True        # on ROCm, triggers MIOpen find for every new shape, slow
+ torch.backends.cudnn.benchmark = False       # use default algorithm, skip find

- dist.init_process_group(...)                 # unconditional call; ROCm torch lacks this function, crashes
+ if hasattr(dist, "init_process_group") and n_gpus > 1 and device.type == "cuda":
+     dist.init_process_group(...)
```

`benchmark=True` on ROCm runs MIOpen find for every new convolution shape. Training shapes change frequently, causing continuous find overhead. `False` uses the default algorithm and skips find.

The ROCm Windows build of torch ships without `torch.distributed` (verified: `dist.is_available()` returns `False`), so the original unconditional call raises `AttributeError`. The guard mirrors the DDP-wrapping condition below it (`n_gpus > 1 and device.type == "cuda"`), so skipping initialization on a single GPU has no side effects.

### 5. `assets/config_template.json`

```diff
- "precision": "fp16"
+ "precision": "bf16"
```

`bf16` is more stable on ROCm (same dynamic range as fp32, no loss scaling needed).

## Known Environment Issue (Important)

> [!WARNING]
> **torch 2.9.1 + rocm 7.2.1 wheel has incomplete gfx1201 kernels**: the default install uses ROCm 7.2.1 / PyTorch 2.9.1 wheels which miss some matmul/softmax/bmm fused kernels for RDNA4 on RX 9070 XT, causing **inference** (`Converting audio chunk` loop) to repeatedly report `CUDA ERROR: no kernel image is available for execution on device` + `[ERROR] device/model/fp is None` spam. **Training usually works** (the training aten subset differs); inference needs a torch/ROCm upgrade.

**Fix**: upgrade to the AMD compatibility matrix official pair `torch 2.13.0 + rocm 10.0.0` (gfx1201+Windows, full pipeline verified; ~5 GB extra). Install: `pip install --no-cache-dir https://stable.repo.amd.com/rocm/whl-next/torch-2.13.0+rocm10.0.0-cp312-cp312-win_amd64.whl ...` (the rest of the wheels live on the same host; see the repo's `applio-rocm10-upgrade` skill for the full procedure).

**Short-term workaround** (only the log is spammed but the audio is still produced — tolerable): ignore the ERROR lines, the inference result is still correct — RVC's `try/except` falls back to a slow CPU path each time a kernel fails, so each chunk is 10–100× slower. If your audio still generates (just slowly), you don't need to upgrade.

**Quick check you're hitting the same issue**: if the error contains `raise GpuError(CUDA ERROR: no kernel image` and your torch is 2.9.1+rocm7.2.1, yes.

## Parameter Constraints

| Parameter | Value | Limit | Reason |
|-----------|-------|-------|--------|
| `x_center` | 5 | ≤ 5 | Actual NSF forward = x_center + 2s, threshold 7-8s |
| `x_query` | 3 | ≤ x_center | Otherwise t-t_query < 0, empty array error |
| `x_max` | 6 | > x_center | Split threshold (only split when audio exceeds it) |

> [!TIP]
> `x_center` determines the chunk size, not `x_max`. `x_max` is only the threshold for "when to start splitting".

## Verified Environment

| Component | Version |
|-----------|---------|
| GPU | AMD Radeon RX 9070 XT (gfx1201) |
| Graphics driver | 26.2.2 or newer |
| ROCm | 7.2.1 (Windows) |
| PyTorch | 2.9.1+rocm7.2.1 |
| Python | 3.12 |
| Applio | 3.6.4 (IAHispano/Applio) |

## FAQ

<details>
<summary><b>Why use different launch methods for inference and training?</b></summary>

Inference has varying convolution shapes; MIOpen find crashes each time. Training has fixed shapes; MIOpen find caches after the first run and is faster than native convolution.

</details>

<details>
<summary><b><code>[WARNING] failed to run offload-arch: binary not found</code>?</b></summary>

Harmless warning. ROCm's GPU architecture detection tool is not found; torch uses a fallback to identify the GPU.

</details>

<details>
<summary><b>Slight metallic/electronic sound in inference?</b></summary>

An inherent characteristic of RVC voice conversion, not a configuration issue. Try lowering `index_rate` (0.3→0.1, or set to 0 to disable indexing) or switching the f0 method (rmvpe→crepe).

</details>

<details>
<summary><b>How to revert the patches?</b></summary>

The patch script backs up originals as `.bak`. Rename the following `.bak` files back:

- `rvc/configs/config.py.bak` → `rvc/configs/config.py`
- `rvc/infer/pipeline.py.bak` → `rvc/infer/pipeline.py`
- `rvc/train/train.py.bak` → `rvc/train/train.py`
- `assets/config_template.json.bak` → `assets/config_template.json`

Then delete `applio_cudnn_off.py`.

</details>

## Acknowledgements

- [IAHispano/Applio](https://github.com/IAHispano/Applio) — Original Applio (MIT License, formerly Applio-RVC-Fork)
- [cantascendia/rocm-rdna4-windows](https://github.com/cantascendia/rocm-rdna4-windows) — ROCm 7.2.1 + PyTorch 2.9.1 Windows installation reference
- [AMD ROCm](https://rocm.docs.amd.com/) — ROCm 7.2.1 Windows support

## License

[MIT](LICENSE)
