<div align="center">

# Applio ROCm RDNA4

**让 [Applio](https://github.com/IAHispano/Applio) 在 AMD RX 9000 系列显卡（gfx1201 / RDNA4）上正常训练与推理**

[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![GPU](https://img.shields.io/badge/GPU-RX%209000%20Series%20%28gfx1201%29-ED1C24)
![ROCm](https://img.shields.io/badge/ROCm-7.2.1-0066CC)
![PyTorch](https://img.shields.io/badge/PyTorch-2.9.1%2Brocm7.2.1-EE4C2C)

[中文](README.md) · [English](README_EN.md)

</div>

原版 Applio 在 RDNA4 显卡上存在 **5 个问题**：推理崩溃、长音频金属破音、中文路径报错、训练报错、训练慢。本仓库提供**一键补丁脚本**修复全部问题，另含 **1 项拼接音质优化**。只改代码，不涉及模型权重。

## 问题与修复

| # | 问题 | 严重度 | 修复方案 | 涉及文件 |
|---|------|--------|----------|----------|
| 1 | 推理时 MIOpen 崩溃 | 严重 | 禁用 cudnn，走 ATen 原生卷积（反而提速） | `applio_cudnn_off.py`（新增） |
| 2 | 长音频金属破音 | 严重 | `x_center=5`，NSF 单次前向 ≈7s（临界 7-8s） | `rvc/configs/config.py` |
| 3 | faiss 不支持中文路径 | 中等 | 非 ASCII 路径自动复制到临时目录再加载 | `rvc/infer/pipeline.py` |
| 4 | 训练 `init_process_group` 报错 | 严重 | `hasattr` 检查，单 GPU 跳过 | `rvc/train/train.py` |
| 5 | 训练慢 | 中等 | `benchmark=False`，避免 MIOpen 反复 find | `rvc/train/train.py` |

> [!NOTE]
> 另含一项音质优化：等功率 sin/cos crossfade（4096 样本 / 85ms）替代原版裸 `np.concatenate`，块拼接过渡更平滑。

## 安装方法

> 二选一：**方法一**是手动逐步安装（适合想完全掌控每一步的进阶用户）；**方法二**是双击脚本一键完成，安装器执行的操作与方法一完全一致——自动装好 Python / ROCm / PyTorch / Applio / 补丁 / 启动器全流程，无需命令行。

### 方法一：手动安装（进阶）

#### Step 1 · 安装 Python 3.12

下载并安装 [Python 3.12](https://www.python.org/downloads/release/python-3120/)（勾选 **Add to PATH**），然后验证：

```cmd
python --version
```

确认输出 `Python 3.12.x`。

#### Step 2 · 安装 ROCm SDK + PyTorch

> [!IMPORTANT]
> 需要 AMD **26.2.2 或更新**的显卡驱动（[AMD 官网下载](https://www.amd.com/en/support)）。

安装 ROCm SDK：

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm-7.2.1.tar.gz
```

安装 PyTorch（ROCm 版，体积较大，需要几分钟）：

```cmd
pip install --no-cache-dir ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1+rocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1+rocm7.2.1-cp312-cp312-win_amd64.whl ^
 https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1+rocm7.2.1-cp312-cp312-win_amd64.whl
```

验证 GPU 识别：

```cmd
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

预期输出类似：

```text
2.9.1+rocm7.2.1 True AMD Radeon RX 9070 XT
```

#### Step 3 · 下载原版 Applio

```cmd
git clone -b 3.6.4 --depth 1 https://github.com/IAHispano/Applio.git
cd Applio
```

> [!NOTE]
> 补丁脚本按 **3.6.4** 的源码精确匹配，请用 `-b 3.6.4` 锁定版本。上游仓库已改名为 `IAHispano/Applio`（旧名 `Applio-RVC-Fork` 会重定向）。其他版本可能导致补丁不命中——脚本会明确警告而不是静默失败。

#### Step 4 · 安装依赖（跳过 torch）

> [!WARNING]
> Applio 的 `requirements.txt` 锁定了 `torch==2.11.0`，直接安装会**覆盖掉 Step 2 装好的 ROCm torch**，必须过滤。

过滤掉 torch 相关行后安装：

```cmd
findstr /v /b "torch==" requirements.txt | findstr /v /b "torchaudio==" | findstr /v /b "torchvision==" > requirements_no_torch.txt
pip install -r requirements_no_torch.txt
```

或者手动：用记事本打开 `requirements.txt`，删掉 `torch==`、`torchaudio==`、`torchvision==` 开头的行，保存后 `pip install -r requirements.txt`。

#### Step 5 · 下载预训练模型

Applio 需要预训练模型（HiFi-GAN 声码器等），有两种方式：

1. **WebUI 下载（推荐）**：启动 Applio（`python app.py --open`），在 WebUI 的「设置」→「训练」里点击下载预训练模型。
2. **手动下载**：按照 [官方文档](https://docs.applio.org/getting-started/pretrained/) 下载，放到 `rvc/models/pretraineds/` 目录。

> [!CAUTION]
> **不要运行官方 `run-install.bat`**。它会创建 Conda 环境并安装非 ROCm 版 torch，**破坏 Step 2 已装好的 ROCm torch 环境**。本指南的安装方式已完全绕开官方安装脚本。

#### Step 6 · 应用 RDNA4 补丁

把本 repo 的两个文件复制到 Applio 目录，然后运行补丁脚本：

```cmd
git clone https://github.com/Ujkur/Applio-rocm-rdna4.git
copy Applio-rocm-rdna4\applio_cudnn_off.py .
copy Applio-rocm-rdna4\apply_rdna4_patches.py .

python apply_rdna4_patches.py
```

脚本自动修改 4 个文件（原文件备份为 `.bak`），并确认 `applio_cudnn_off.py` 就位。看到 `完成!` 即表示成功；若某处未命中（通常是 Applio 版本不对），脚本会明确列出问题并以非零码退出。脚本可重复运行，已打过的补丁会自动跳过。

### 方法二：一键安装（推荐）

> 双击一个脚本自动完成全部安装，全程无需命令行。支持断点续传与重复运行——中断后重新双击即可，已完成的步骤会自动跳过。

**前提**：Windows 10/11 64 位 · AMD RX 9000 系列显卡 · [驱动 ≥ 26.2.2](https://www.amd.com/en/support) · 约 20 GB 磁盘 · 全程联网（首次下载约 3 GB，安装后约 10 GB）

1. 点击本页绿色 **Code** 按钮 → **Download ZIP**，解压到任意位置（或直接 `git clone` 本仓库）
2. 双击解压目录里的 **install.bat**
   - 若弹出「Windows 已保护你的电脑」：点「更多信息」→「仍要运行」
   - 全程自动，约 20–60 分钟（取决于网速），期间请勿关闭窗口
3. 桌面出现两个图标，**注意不要混用**：

| 图标 | 用途 | 内部行为 |
|---|---|---|
| **Applio 推理** | 变声 / 推理 | `applio_cudnn_off.py`，cudnn 关闭 |
| **Applio 训练** | 训练模型 | `app.py`，cudnn 开启 + MIOpen 环境变量自动注入 |

安装器把 Python 3.12、ROCm 7.2.1、PyTorch 2.9.1+rocm、Applio 3.6.4、全部依赖与 RDNA4 补丁装进一个独立目录（默认 `C:\Applio-RDNA4`）。**不修改系统 Python、不写 PATH、不动注册表、不需要管理员权限**，删除目录即完全卸载。安装成功后自动删除下载缓存目录（`C:\Applio-RDNA4-cache`），释放约 2.5 GB 空间。

- 自定义安装位置：`install.bat D:\Applio-RDNA4`
- 卸载：双击 `uninstall.bat`
- 安装中断：直接重新运行 `install.bat`，大文件断点续传
- 预训练模型：首次启动后在 WebUI「设置 → 训练」里下载（启动器已内置 hf-mirror 国内镜像，一般可直接成功；失败需科学上网）

## 验证安装

本 repo 自带 4 个测试脚本，用来确认环境、补丁、推理路径、训练路径都正常。全部 `[PASS]`（退出码 0）即通过：

| 脚本 | 验证内容 | 运行位置 |
|------|----------|----------|
| `tests/check_environment.py` | Python 3.12、ROCm torch、GPU 识别、bf16 计算 | 任意目录 |
| `tests/check_patches.py` | 5 项补丁全部落点、patched 文件可编译、faiss 中文路径实测 | Applio 根目录（或把路径作为参数传入） |
| `tests/check_inference.py` | 推理路径：cudnn-off + 变 shape 卷积 + bf16 | 任意目录 |
| `tests/check_training.py` | 训练路径：cudnn-on + MIOpen + bf16 真实训练步 | 任意目录 |

在 Applio 根目录下运行（假设本 repo 已按方法一 Step 6 clone 到 `Applio-rocm-rdna4\` 子目录）：

```cmd
python Applio-rocm-rdna4\tests\check_environment.py
python Applio-rocm-rdna4\tests\check_patches.py .
python Applio-rocm-rdna4\tests\check_inference.py
python Applio-rocm-rdna4\tests\check_training.py
```

> [!TIP]
> `check_training.py` 会自动设置 MIOpen 环境变量并探测 LLVM 路径，不需要先手动 set。`check_patches.py` 不带参数时默认检查当前目录。

## 使用方法

| 场景 | 启动命令 | cudnn | 原因 |
|------|----------|-------|------|
| **推理** | `python applio_cudnn_off.py --open` | 关闭 | 卷积 shape 多变，MIOpen 每次 find 都会崩溃 |
| **训练** | `python app.py --open` | 开启 | shape 固定，MIOpen find 一次后缓存，比原生卷积快 |

训练前先设置 MIOpen 环境变量：

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

> [!WARNING]
> **两个入口不要混用**：训练用 cudnn-off 会慢，推理用 cudnn-on 会崩溃。

## 修改详解

### 1. `applio_cudnn_off.py`（新增）

推理入口脚本，在 `app.py` 启动前执行 `torch.backends.cudnn.enabled = False`。

### 2. `rvc/configs/config.py`

```diff
- x_pad, x_query, x_center, x_max = (1, 6, 38, 41)   # 原版：每块 38s，后段金属破音
+ x_pad, x_query, x_center, x_max = (1, 3, 5, 6)     # RDNA4：每块约 5s，安全
```

`x_center` 决定每块大小（切点步长）。实际 NSF 前向长度 ≈ `x_center + 2s`（padding）。临界点 7-8s，超过后后段出现金属破音。`x_center=5` 实际 7s，安全。`config.py` 里有两处该参数（默认档和低显存档 `(1, 5, 30, 32)`），脚本会一并替换。

### 3. `rvc/infer/pipeline.py`

- **crossfade（优化）**：原版裸 `np.concatenate` → 等功率 sin/cos crossfade（4096 样本 / 85ms），提升块拼接过渡质量
- **faiss 中文路径**：`faiss.read_index` 用 C `fopen`，不支持中文/全角路径。检测到非 ASCII 路径时自动复制到临时目录再加载
- 新增 `import tempfile, shutil`

### 4. `rvc/train/train.py`

```diff
- torch.backends.cudnn.benchmark = True        # ROCm 上每个新 shape 都触发 MIOpen find，慢
+ torch.backends.cudnn.benchmark = False       # 用默认算法，跳过 find

- dist.init_process_group(...)                 # 无条件调用，ROCm torch 无此函数，必崩
+ if hasattr(dist, "init_process_group") and n_gpus > 1 and device.type == "cuda":
+     dist.init_process_group(...)
```

`benchmark=True` 在 ROCm 上会对每个新卷积 shape 执行 MIOpen find 搜索最优算法，训练时 shape 频繁变化导致持续 find 开销。`False` 用默认算法跳过 find。

ROCm Windows 版 torch 不含 `torch.distributed`（实测 `dist.is_available()` 为 `False`），原版的无条件调用会直接 `AttributeError`。守卫条件与下方 DDP 包装的条件（`n_gpus > 1 and device.type == "cuda"`）保持一致，单 GPU 跳过初始化无任何影响。

### 5. `assets/config_template.json`

```diff
- "precision": "fp16"
+ "precision": "bf16"
```

`bf16` 在 ROCm 上更稳定（动态范围同 fp32，无需 loss scaling）。

## 参数约束

| 参数 | 值 | 上限 | 原因 |
|------|-----|------|------|
| `x_center` | 5 | ≤ 5 | 实际 NSF 前向 = x_center + 2s，临界 7-8s |
| `x_query` | 3 | ≤ x_center | 否则切点搜索 t-t_query < 0，空数组报错 |
| `x_max` | 6 | > x_center | 分块阈值（音频超过才分块） |

> [!TIP]
> `x_center` 决定每块大小，不是 `x_max`。`x_max` 只是"音频超过多少秒才分块"的阈值。

## 已验证环境

| 组件 | 版本 |
|------|------|
| GPU | AMD Radeon RX 9070 XT（gfx1201） |
| 显卡驱动 | 26.2.2 或更新 |
| ROCm | 7.2.1（Windows） |
| PyTorch | 2.9.1+rocm7.2.1 |
| Python | 3.12 |
| Applio | 3.6.4（IAHispano/Applio） |

## FAQ

<details>
<summary><b>为什么推理和训练要用不同的启动方式？</b></summary>

推理时卷积 shape 多变，MIOpen 每次 find 会崩溃。训练时 shape 固定，MIOpen find 一次后缓存，比原生卷积快。

</details>

<details>
<summary><b><code>[WARNING] failed to run offload-arch: binary not found</code> 怎么办？</b></summary>

无害警告，不影响使用。ROCm 的 GPU 架构检测工具找不到，torch 用 fallback 识别 GPU。

</details>

<details>
<summary><b>推理有轻微金属音/电音？</b></summary>

RVC 变声的固有特性，不是配置问题。可尝试降低 `index_rate`（0.3→0.1，或设为 0 完全禁用索引）或换 f0 方法（rmvpe→crepe）。

</details>

<details>
<summary><b>如何回退补丁？</b></summary>

补丁脚本自动备份为 `.bak`。把以下文件的 `.bak` 改回原名即可：

- `rvc/configs/config.py.bak` → `rvc/configs/config.py`
- `rvc/infer/pipeline.py.bak` → `rvc/infer/pipeline.py`
- `rvc/train/train.py.bak` → `rvc/train/train.py`
- `assets/config_template.json.bak` → `assets/config_template.json`

然后删除 `applio_cudnn_off.py`。

</details>

## 致谢

- [IAHispano/Applio](https://github.com/IAHispano/Applio) — Applio 原版（MIT License，旧名 Applio-RVC-Fork）
- [cantascendia/rocm-rdna4-windows](https://github.com/cantascendia/rocm-rdna4-windows) — ROCm 7.2.1 + PyTorch 2.9.1 Windows 安装方法参考
- [AMD ROCm](https://rocm.docs.amd.com/) — ROCm 7.2.1 Windows 支持

## License

[MIT](LICENSE)
