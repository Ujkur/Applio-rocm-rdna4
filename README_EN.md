[中文](README.md) | [English](README_EN.md)

# Applio ROCm RDNA4

Patch guide and one-click script for using [Applio](https://github.com/IAHispano/Applio-RVC-Fork) on AMD RX 9000 series (gfx1201 / RDNA4).

The original Applio has 5 issues on RDNA4 GPUs. This guide provides a one-click patch script to fix all of them, plus 1 stitching optimization.

---

## Issues and Fixes

| # | Issue | Severity | Fix | Modified File |
|---|-------|----------|-----|---------------|
| 1 | MIOpen crash during inference | Critical | Disable cudnn, use ATen native convolution (significant speedup) | `applio_cudnn_off.py` (new) |
| 2 | Metallic artifacts on long audio | Critical | `x_center=5`, NSF forward <7s | `rvc/configs/config.py` |
| 3 | faiss doesn't support CJK paths | Medium | Auto-copy to temp ASCII path | `rvc/infer/pipeline.py` |
| 4 | Training `init_process_group` error | Critical | `hasattr` check, skip for single GPU | `rvc/train/train.py` |
| 5 | Slow training | Medium | `benchmark=False` to avoid MIOpen find | `rvc/train/train.py` |

Also includes an optimization: equal-power crossfade (4096 samples/85ms) replacing bare `np.concatenate` for better chunk stitching quality.

---

## Installation

### Step 1 — Install Python 3.12

Download [Python 3.12](https://www.python.org/downloads/release/python-3120/) and install (check "Add to PATH").

```cmd
python --version
```

Confirm output shows `Python 3.12.x`.

### Step 2 — Install ROCm SDK + PyTorch

Requires AMD 26.2.2 or newer graphics driver ([AMD website](https://www.amd.com/en/support)).

Install ROCm SDK:

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm-7.2.1.tar.gz
```

Install PyTorch (ROCm version, may take several minutes):

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl
```

Verify:

```cmd
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Confirm output is similar to `2.9.1+rocm7.2.1 True AMD Radeon RX 9070 XT`.

### Step 3 — Download original Applio

```cmd
git clone https://github.com/IAHispano/Applio-RVC-Fork.git
cd Applio-RVC-Fork
```

### Step 4 — Install dependencies (skip torch)

**Note**: Applio's `requirements.txt` contains `torch==2.11.0`. Installing it directly will overwrite the ROCm torch you just installed. You must skip it.

Filter out torch-related lines before installing:

```cmd
findstr /v /b "torch==" requirements.txt | findstr /v /b "torchaudio==" | findstr /v /b "torchvision==" > requirements_no_torch.txt
pip install -r requirements_no_torch.txt
```

Or manually open `requirements.txt` in Notepad, delete lines starting with `torch==`, `torchaudio==`, `torchvision==`, save, then `pip install -r requirements.txt`.

### Step 5 — Download pretrained models

Applio requires pretrained models (HiFi-GAN vocoder, etc.). Two options:

1. **WebUI download (recommended)**: Launch Applio (`python app.py --open`), then download pretrained models in the WebUI under "Settings" → "Training".
2. **Manual download**: Download from [official docs](https://docs.applio.org/getting-started/pretrained/) and place in `rvc/models/pretraineds/`.

> **⚠️ Do not run the official `run-install.bat`**. It creates a Conda environment and installs non-ROCm torch, **which will break the ROCm torch environment set up in Step 2**. This guide's installation completely bypasses the official install script.

### Step 6 — Apply RDNA4 patches

Copy the two files from this repo to the Applio directory:

```cmd
git clone https://github.com/Ujkur/Applio-rocm-rdna4.git
copy Applio-rocm-rdna4\applio_cudnn_off.py .
copy Applio-rocm-rdna4\apply_rdna4_patches.py .

python apply_rdna4_patches.py
```

The script automatically modifies 5 files and backs up originals as `.bak`. Seeing `Done!` means success.

---

## Usage

### Inference (cudnn-off)

```cmd
python applio_cudnn_off.py --open
```

`applio_cudnn_off.py` disables cudnn(MIOpen) at startup and uses ATen native convolution. Inference must use this entry point — MIOpen crashes on gfx1201.

### Training (cudnn-on + MIOpen)

```cmd
set MIOPEN_USER_DB_PATH=%USERPROFILE%\.miopen_applio
set MIOPEN_DEBUG_CONV_FFT=0
set MIOPEN_FIND_MODE=FAST
python app.py --open
```

If MIOpen reports clang not found during training, set the LLVM path:

```cmd
set "PATH=<Python_install_path>\Lib\site-packages\_rocm_sdk_core\lib\llvm\bin;%PATH%"
```

**Use `applio_cudnn_off.py` for inference (cudnn off) and `app.py` for training (cudnn on). Do not mix them.** Training with cudnn-off is slow; inference with cudnn-on crashes.

---

## Modification Details

### 1. `applio_cudnn_off.py` (new)

Inference entry script that executes `torch.backends.cudnn.enabled = False` before `app.py` starts.

### 2. `rvc/configs/config.py`

```python
# Original default (38s per chunk, causes metallic artifacts)
x_pad, x_query, x_center, x_max = (1, 6, 38, 41)

# RDNA4 patch (~5s per chunk, safe)
x_pad, x_query, x_center, x_max = (1, 3, 5, 6)
```

`x_center` determines chunk size (split step). Actual NSF forward length ≈ `x_center + 2s` (padding). Critical threshold is 7-8s; exceeding it causes metallic artifacts in the latter part. `x_center=5` gives actual 7s, safe.

### 3. `rvc/infer/pipeline.py`

- **crossfade (optimization)**: bare `np.concatenate` → equal-power sin/cos crossfade (4096 samples/85ms), improves chunk stitching quality
- **faiss CJK path**: `faiss.read_index` uses C `fopen` which doesn't support CJK/full-width paths. Non-ASCII paths are auto-copied to a temp directory before loading
- Added `import tempfile, shutil`

### 4. `rvc/train/train.py`

```python
# Original
torch.backends.cudnn.benchmark = True       # ROCm: find on every new shape, slow
dist.init_process_group(...)                 # unconditional call, ROCm torch may lack this

# RDNA4 patch
torch.backends.cudnn.benchmark = False                    # use default algorithm, skip find
if hasattr(dist, "init_process_group") and n_gpus > 1:    # ROCm torch may lack this function
    dist.init_process_group(...)
```

`benchmark=True` on ROCm triggers MIOpen find for every new convolution shape. Training shapes change frequently, causing continuous find overhead. `False` uses the default algorithm and skips find.

### 5. `assets/config_template.json`

```json
"precision": "bf16"
```

Original `fp16`; `bf16` is more stable on ROCm (same dynamic range as fp32, no loss scaling needed).

---

## Parameter Constraints

| Parameter | Value | Upper limit | Reason |
|-----------|-------|-------------|--------|
| `x_center` | 5 | ≤ 5 | Actual NSF forward = x_center + 2s, threshold 7-8s |
| `x_query` | 3 | ≤ x_center | Otherwise t-t_query < 0, empty array error |
| `x_max` | 6 | > x_center | Split threshold (only split when audio exceeds) |

`x_center` determines chunk size, not `x_max`. `x_max` is only the threshold for "when to start splitting".

---

## FAQ

**Q: Why use different launch methods for inference and training?**

Inference has varying convolution shapes; MIOpen find crashes each time. Training has fixed shapes; MIOpen find caches after the first run and is faster than native convolution.

**Q: `[WARNING] failed to run offload-arch: binary not found`?**

Harmless warning. ROCm's GPU architecture detection tool is not found; torch uses a fallback to identify the GPU.

**Q: Slight metallic/electronic sound in inference?**

Inherent characteristic of RVC voice conversion, not a configuration issue. Try lowering `index_rate` (0.3→0.1, or set to 0 to disable indexing) or switching f0 method (rmvpe→crepe).

**Q: How to revert patches?**

The patch script backs up originals as `.bak`. Rename the following `.bak` files back:
- `rvc/configs/config.py.bak` → `rvc/configs/config.py`
- `rvc/infer/pipeline.py.bak` → `rvc/infer/pipeline.py`
- `rvc/train/train.py.bak` → `rvc/train/train.py`
- `assets/config_template.json.bak` → `assets/config_template.json`

Then delete `applio_cudnn_off.py`.

---

## Acknowledgements

- [IAHispano/Applio-RVC-Fork](https://github.com/IAHispano/Applio-RVC-Fork) — Original Applio (MIT License)
- [cantascendia/rocm-rdna4-windows](https://github.com/cantascendia/rocm-rdna4-windows) — ROCm 7.2.1 + PyTorch 2.9.1 Windows installation reference
- [AMD ROCm](https://rocm.docs.amd.com/) — ROCm 7.2.1 Windows support

## License

MIT
