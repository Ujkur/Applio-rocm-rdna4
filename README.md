[中文](README.md) | [English](README_EN.md)

# Applio ROCm RDNA4

在 AMD RX 9000 系列 (gfx1201 / RDNA4) 上使用 [Applio](https://github.com/IAHispano/Applio-RVC-Fork) 的补丁指南和一键脚本。

原版 Applio 在 RDNA4 显卡上有 5 个问题，本指南提供一键补丁脚本解决全部，另含 1 项拼接优化。

---

## 问题与解决

| # | 问题 | 严重度 | 解决方案 | 修改文件 |
|---|------|--------|---------|---------|
| 1 | 推理时 MIOpen 崩溃 | 严重 | 禁用 cudnn，走 ATen 原生卷积（显著提速） | `applio_cudnn_off.py` (新增) |
| 2 | 长音频金属破音 | 严重 | `x_center=5`，NSF 前向 <7s | `rvc/configs/config.py` |
| 3 | faiss 不支持中文路径 | 中等 | 自动复制到临时 ASCII 路径 | `rvc/infer/pipeline.py` |
| 4 | 训练 `init_process_group` 报错 | 严重 | `hasattr` 检查，单 GPU 跳过 | `rvc/train/train.py` |
| 5 | 训练慢 | 中等 | `benchmark=False` 避免 MIOpen find | `rvc/train/train.py` |

此外包含一项优化：等功率 crossfade（4096样本/85ms）替代裸 `np.concatenate`，提升块拼接过渡质量。

---

## 安装步骤

### Step 1 — 安装 Python 3.12

下载 [Python 3.12](https://www.python.org/downloads/release/python-3120/) 并安装（勾选 Add to PATH）。

```cmd
python --version
```

确认输出 `Python 3.12.x`。

### Step 2 — 安装 ROCm SDK + PyTorch

需要 AMD 26.2.2 或更新显卡驱动（[AMD 官网下载](https://www.amd.com/en/support)）。

安装 ROCm SDK：

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm-7.2.1.tar.gz
```

安装 PyTorch（ROCm 版，这一步可能需要几分钟）：

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl
```

验证：

```cmd
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

确认输出类似 `2.9.1+rocm7.2.1 True AMD Radeon RX 9070 XT`。

### Step 3 — 下载原版 Applio

```cmd
git clone https://github.com/IAHispano/Applio-RVC-Fork.git
cd Applio-RVC-Fork
```

### Step 4 — 安装依赖（跳过 torch）

**注意**：Applio 的 `requirements.txt` 里有 `torch==2.11.0`，直接安装会覆盖刚装好的 ROCm torch，必须跳过。

过滤掉 torch 相关行后安装：

```cmd
findstr /v /b "torch==" requirements.txt | findstr /v /b "torchaudio==" | findstr /v /b "torchvision==" > requirements_no_torch.txt
pip install -r requirements_no_torch.txt
```

或者手动用记事本打开 `requirements.txt`，删掉 `torch==`、`torchaudio==`、`torchvision==` 开头的行，保存后 `pip install -r requirements.txt`。

### Step 5 — 下载预训练模型

Applio 需要预训练模型（HiFi-GAN 声码器等）。按照 [官方文档](https://docs.applio.org/getting-started/pretrained/) 下载，放到 `rvc/models/pretraineds/` 目录。

或运行官方 `run-install.bat`（会下载模型，但同时会创建 Conda 环境；模型下载完成后可删除 `env/` 目录，不影响使用）。

### Step 6 — 应用 RDNA4 补丁

把本 repo 的两个文件复制到 Applio 目录：

```cmd
git clone https://github.com/Ujkur/Applio-rocm-rdna4.git
copy Applio-rocm-rdna4\applio_cudnn_off.py .
copy Applio-rocm-rdna4\apply_rdna4_patches.py .

python apply_rdna4_patches.py
```

脚本会自动修改 5 个文件，原文件备份为 `.bak`。看到 `完成!` 即表示成功。

---

## 使用方法

### 推理（cudnn-off）

```cmd
python applio_cudnn_off.py --open
```

`applio_cudnn_off.py` 在启动时禁用 cudnn(MIOpen)，走 ATen 原生卷积。推理必须用这个入口——MIOpen 在 gfx1201 上会崩溃。

### 训练（cudnn-on + MIOpen）

```cmd
set MIOPEN_USER_DB_PATH=%USERPROFILE%\.miopen_applio
set MIOPEN_DEBUG_CONV_FFT=0
set MIOPEN_FIND_MODE=FAST
python app.py --open
```

如果训练时 MIOpen 报错找不到 clang，需要额外设置 LLVM 路径：

```cmd
set "PATH=<Python安装路径>\Lib\site-packages\_rocm_sdk_core\lib\llvm\bin;%PATH%"
```

**推理用 `applio_cudnn_off.py`（cudnn off），训练用 `app.py`（cudnn on），不要混用。** 训练用 cudnn-off 会慢，推理用 cudnn-on 会崩溃。

---

## 修改详解

### 1. `applio_cudnn_off.py`（新增）

推理入口脚本，在 `app.py` 启动前执行 `torch.backends.cudnn.enabled = False`。

### 2. `rvc/configs/config.py`

```python
# 原版默认（每块38秒，会金属破音）
x_pad, x_query, x_center, x_max = (1, 6, 38, 41)

# RDNA4 修改（每块约5秒，安全）
x_pad, x_query, x_center, x_max = (1, 3, 5, 6)
```

`x_center` 决定每块大小（切点步长）。实际 NSF 前向长度 ≈ `x_center + 2s`（padding）。临界点 7-8s，超过后段金属破音。`x_center=5` 实际 7s，安全。

### 3. `rvc/infer/pipeline.py`

- **crossfade（优化）**：原版裸 `np.concatenate` → 等功率 sin/cos crossfade（4096样本/85ms），提升块拼接过渡质量
- **faiss 中文路径**：`faiss.read_index` 用 C `fopen`，不支持中文/全角路径。检测到非 ASCII 路径时自动复制到临时目录再加载
- 新增 `import tempfile, shutil`

### 4. `rvc/train/train.py`

```python
# 原版
torch.backends.cudnn.benchmark = True       # ROCm 上每个新 shape 都 find，慢
dist.init_process_group(...)                 # 无条件调用，ROCm torch 可能无此函数

# RDNA4 修改
torch.backends.cudnn.benchmark = False                    # 用默认算法，跳过 find
if hasattr(dist, "init_process_group") and n_gpus > 1:    # ROCm torch 可能缺失此函数
    dist.init_process_group(...)
```

`benchmark=True` 在 ROCm 上会对每个新卷积 shape 执行 MIOpen find 搜索最优算法，训练时 shape 频繁变化导致持续 find 开销。`False` 用默认算法跳过 find。

### 5. `assets/config_template.json`

```json
"precision": "bf16"
```

原版 `fp16`，ROCm 上 `bf16` 更稳定（动态范围同 fp32，无需 loss scaling）。

---

## 参数约束

| 参数 | 值 | 上限 | 原因 |
|------|-----|------|------|
| `x_center` | 5 | ≤ 5 | 实际 NSF 前向 = x_center + 2s，临界 7-8s |
| `x_query` | 3 | ≤ x_center | 否则切点搜索 t-t_query < 0，空数组报错 |
| `x_max` | 6 | > x_center | 分块阈值（音频超过才分块） |

`x_center` 决定每块大小，不是 `x_max`。`x_max` 只是"音频超过多少秒才分块"的阈值。

---

## FAQ

**Q: 为什么推理和训练要用不同的启动方式？**

推理时卷积 shape 多变，MIOpen 每次 find 会崩溃。训练时 shape 固定，MIOpen find 一次后缓存，比原生卷积快。

**Q: `[WARNING] failed to run offload-arch: binary not found` 怎么办？**

无害警告，不影响使用。ROCm 的 GPU 架构检测工具找不到，torch 用 fallback 识别 GPU。

**Q: 推理有轻微金属音/电音？**

RVC 变声的固有特性，不是配置问题。可尝试降低 `index_rate`（0.3→0.1，或设为 0 完全禁用索引）或换 f0 方法（rmvpe→crepe）。

**Q: 如何回退补丁？**

补丁脚本自动备份为 `.bak`。把以下文件的 `.bak` 改回原名即可：
- `rvc/configs/config.py.bak` → `rvc/configs/config.py`
- `rvc/infer/pipeline.py.bak` → `rvc/infer/pipeline.py`
- `rvc/train/train.py.bak` → `rvc/train/train.py`
- `assets/config_template.json.bak` → `assets/config_template.json`

然后删除 `applio_cudnn_off.py`。

---

## 致谢

- [IAHispano/Applio-RVC-Fork](https://github.com/IAHispano/Applio-RVC-Fork) — Applio 原版 (MIT License)
- [cantascendia/rocm-rdna4-windows](https://github.com/cantascendia/rocm-rdna4-windows) — ROCm 7.2.1 + PyTorch 2.9.1 Windows 安装方法参考
- [AMD ROCm](https://rocm.docs.amd.com/) — ROCm 7.2.1 Windows 支持

## License

MIT
