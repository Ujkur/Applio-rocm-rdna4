#!/usr/bin/env python3
"""Applio RDNA4 (gfx1201) 补丁脚本
在原版 Applio 根目录运行: python apply_rdna4_patches.py
自动应用所有 RDNA4 优化修改。修改前自动备份原文件（.bak）。
可重复运行：已打过的补丁会自动跳过。针对 Applio 3.6.4 源码匹配。
"""
import os, sys, re, json, shutil

WARNINGS = []


def backup(path):
    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def replace_checked(content, old, new, label):
    """精确替换并校验命中；仅替换第一处，多处匹配时记录警告而不是全部替换。"""
    count = content.count(old)
    if count == 0:
        WARNINGS.append(label + ": 未找到目标代码（Applio 版本可能不是 3.6.4，请手动检查）")
        return content
    if count > 1:
        WARNINGS.append(label + f": 找到 {count} 处匹配，仅替换第一处，请手动检查其余位置")
    return content.replace(old, new, 1)


def main():
    if not os.path.isfile("app.py") or not os.path.isdir("rvc"):
        print("错误: 请在 Applio 根目录运行此脚本（需有 app.py 和 rvc/）")
        sys.exit(1)

    print("Applio RDNA4 (gfx1201) 补丁脚本 (针对 3.6.4)")
    print("=" * 50)

    # 1. config.py: x_center=5
    # 注意：config.py 里有两处该参数（默认档 (1,6,38,41) 和低显存档 (1,5,30,32)），
    # 两处都必须替换（README 已明确记录此行为），所以这里不能用 count=1。
    p = "rvc/configs/config.py"
    c = read(p)
    presets = re.findall(r"x_pad, x_query, x_center, x_max = \([^)]+\)", c)
    if presets and all(preset.endswith("(1, 3, 5, 6)") for preset in presets):
        print("[1/8] config.py: 已是 (1,3,5,6)，跳过")
    else:
        backup(p)
        c, n = re.subn(
            r"x_pad, x_query, x_center, x_max = \([^)]+\)",
            "x_pad, x_query, x_center, x_max = (1, 3, 5, 6)",
            c,
        )
        if n == 0:
            WARNINGS.append("config.py: 未找到分块参数（Applio 版本可能不是 3.6.4）")
        else:
            write(p, c)
            print(f"[1/8] config.py: x_center=5 (抗金属破音, 实际NSF前向~7s<临界7-8s), 命中{n}处")

    # 2. pipeline.py: crossfade + faiss中文路径 + import
    p = "rvc/infer/pipeline.py"
    c = read(p)
    changed = False
    if "import tempfile" not in c:
        c2 = replace_checked(
            c,
            "import sys\nimport torch",
            "import sys\nimport shutil\nimport tempfile\nimport torch",
            "pipeline.py imports",
        )
        changed |= c2 != c
        c = c2
    # 注意：幂等性检测保留 "fade_len"——它能同时识别脚本打的补丁和手动打过的补丁，
    # 避免对已打补丁的安装重复套用导致嵌套损坏。
    if "fade_len" in c:
        print("[2/8] pipeline.py: crossfade 已存在，跳过")
    else:
        old_concat = "        audio_opt = np.concatenate(audio_opt)"
        new_crossfade = '''        # RDNA4: 等功率crossfade(4096/85ms) 替代裸concatenate
        audio_opt = [np.asarray(chunk) for chunk in audio_opt]
        if len(audio_opt) > 1:
            min_chunk_len = min(len(chunk) for chunk in audio_opt)
            fade_len = min(4096, min_chunk_len // 3)
            if fade_len >= 2:
                result = np.array(audio_opt[0], copy=True)
                for i in range(1, len(audio_opt)):
                    next_chunk = audio_opt[i]
                    fade_t = np.linspace(0, np.pi / 2, fade_len)
                    fade_in = np.sin(fade_t)
                    fade_out = np.cos(fade_t)
                    result[-fade_len:] = (result[-fade_len:] * fade_out + next_chunk[:fade_len] * fade_in)
                    result = np.concatenate([result, next_chunk[fade_len:]])
                audio_opt = result
            else:
                audio_opt = np.concatenate(audio_opt)
        else:
            audio_opt = np.array(audio_opt[0], copy=True)'''
        c2 = replace_checked(c, old_concat, new_crossfade, "pipeline.py crossfade")
        changed |= c2 != c
        c = c2
    if "mkdtemp" in c:
        print("       pipeline.py: faiss 中文路径补丁已存在，跳过")
    else:
        old_faiss = "                index = faiss.read_index(file_index)\n                big_npy = index.reconstruct_n"
        new_faiss = '''                try:
                    file_index.encode("ascii")
                except UnicodeEncodeError:
                    tmp_dir = tempfile.mkdtemp(prefix="faiss_")
                    try:
                        ascii_path = os.path.join(tmp_dir, "index")
                        shutil.copy2(file_index, ascii_path)
                        index = faiss.read_index(ascii_path)
                    finally:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                else:
                    index = faiss.read_index(file_index)
                big_npy = index.reconstruct_n'''
        c2 = replace_checked(c, old_faiss, new_faiss, "pipeline.py faiss")
        changed |= c2 != c
        c = c2
    if changed:
        backup(p)
        write(p, c)
        print("[2/8] pipeline.py: crossfade(4096等功率) + faiss中文路径 + import")

    # 3. train.py: benchmark + distributed
    p = "rvc/train/train.py"
    c = read(p)
    changed = False
    if "torch.backends.cudnn.benchmark = False" in c:
        print("[3/8] train.py: benchmark 已是 False，跳过")
    else:
        c2 = replace_checked(
            c,
            "torch.backends.cudnn.benchmark = True",
            "torch.backends.cudnn.benchmark = False",
            "train.py benchmark",
        )
        changed |= c2 != c
        c = c2
    # 两种守卫写法都视为已打补丁（hasattr 为本脚本写法，dist.is_available 为手动补丁常见写法）
    if 'hasattr(dist, "init_process_group")' in c or "dist.is_available()" in c:
        print("       train.py: distributed 条件已存在，跳过")
    else:
        # 匹配整个 dist.init_process_group(...) 调用块（含多行），统一重缩进后再加 if 守卫，
        # 避免只给首行加缩进造成的错误层级。
        m = re.search(
            r"^([ \t]*)dist\.init_process_group\(.*?\n\1\)",
            c,
            re.DOTALL | re.MULTILINE,
        )
        if m is None:
            # 回退：单行调用写法
            m = re.search(r"^([ \t]*)dist\.init_process_group\([^\n]*\)", c, re.MULTILINE)
        if m is None:
            WARNINGS.append("train.py: 未找到 dist.init_process_group 调用")
        else:
            indent = m.group(1)
            call = m.group(0)
            indented_call = "\n".join(
                ("    " + line) if line.strip() else line for line in call.split("\n")
            )
            replacement = (
                f'{indent}if hasattr(dist, "init_process_group") and n_gpus > 1 and device.type == "cuda":\n'
                + indented_call
            )
            c = c[: m.start()] + replacement + c[m.end() :]
            changed = True
    if changed:
        backup(p)
        write(p, c)
        print("[3/8] train.py: benchmark=False + distributed条件(单GPU跳过)")

    # 4. config_template.json: bf16
    p = "assets/config_template.json"
    with open(p, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("precision") == "bf16":
        print("[4/8] config_template.json: 已是 bf16，跳过")
    else:
        backup(p)
        cfg["precision"] = "bf16"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("[4/8] config_template.json: precision=bf16")

    # 5. prerequisites_download.py: 预训练下载源 huggingface.co -> hf-mirror.com
    # 原版 url_base 硬编码 huggingface.co（requests 直连，不走 HF_ENDPOINT 环境变量），
    # 国内网络首次启动下载 rmvpe/fcpe/contentvec/ffmpeg 等预训练必超时。改为国内镜像。
    p = "rvc/lib/tools/prerequisites_download.py"
    if not os.path.isfile(p):
        WARNINGS.append("prerequisites_download.py 不存在（Applio 版本可能不是 3.6.4）")
    else:
        c = read(p)
        if "hf-mirror.com" in c:
            print("[5/8] prerequisites_download.py: 已是 hf-mirror.com，跳过")
        else:
            old_url = 'url_base = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources"'
            new_url = 'url_base = "https://hf-mirror.com/IAHispano/Applio/resolve/main/Resources"'
            if old_url in c:
                backup(p)
                write(p, c.replace(old_url, new_url))
                print("[5/8] prerequisites_download.py: url_base -> hf-mirror.com (国内镜像)")
            else:
                WARNINGS.append("prerequisites_download.py: 未找到原版 url_base 行")

    # 6. prerequisites_download.py: download_file 断流健壮性（自动重试 + 失败清理坏文件）
    # 原版 requests.get 一次性拉取，无重试无超时；断流(Connection broken/IncompleteRead)时
    # 留下不完整文件且 download_mapping_files 的 os.path.exists 会把坏文件误判为"已存在"。
    # 多次实测：hf-mirror 大文件(~140MB)偶发断流 → 崩溃 + 坏文件残留，重跑也跳过坏文件。
    p = "rvc/lib/tools/prerequisites_download.py"
    if not os.path.isfile(p):
        WARNINGS.append("prerequisites_download.py 不存在（Applio 版本可能不是 3.6.4）")
    else:
        c = read(p)
        if "_attempt" in c:
            print("[6/8] prerequisites_download.py: 断流重试补丁已存在，跳过")
        else:
            old_fn = """    dir_name = os.path.dirname(destination_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    response = requests.get(url, stream=True)
    block_size = 1024
    with open(destination_path, "wb") as file:
        for data in response.iter_content(block_size):
            file.write(data)
            global_bar.update(len(data))"""
            new_fn = """    dir_name = os.path.dirname(destination_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    # RDNA4: 断流自动重试(5次,带超时) + 失败删除不完整文件,避免坏文件被 exists 误判跳过
    for _attempt in range(5):
        try:
            with requests.get(url, stream=True, timeout=(15, 120)) as response:
                response.raise_for_status()
                with open(destination_path, "wb") as file:
                    for data in response.iter_content(1024):
                        file.write(data)
                        global_bar.update(len(data))
            return
        except Exception:
            try:
                os.remove(destination_path)
            except OSError:
                pass
            if _attempt == 4:
                raise"""
            if old_fn in c:
                backup(p)
                write(p, c.replace(old_fn, new_fn))
                print("[6/8] prerequisites_download.py: download_file 断流重试 + 失败清理")
            else:
                WARNINGS.append("prerequisites_download.py: 未找到原版 download_file 函数体")

    # 7. applio_cudnn_off.py
    if os.path.isfile("applio_cudnn_off.py"):
        print("[7/8] applio_cudnn_off.py: 已存在")
    else:
        WARNINGS.append("applio_cudnn_off.py 不在当前目录，请从本 repo 复制后再运行推理")

    # 8. train.py: 训练稳定套装（NaN 守卫 + 梯度裁剪 + DataLoader 单进程）
    # 上游训练循环没有梯度裁剪/NaN 保护。实测（2026-09-03，同一素材在 ROCm 7.2.1 与
    # ROCm 10.0 均崩于 epoch ~13-20，与栈无关）崩溃分两种：
    # A 型：一步坏梯度经 Adam 一步污染全部权重（NaN 守卫可防）；
    # B 型：小数据集 GAN 记忆崩溃（d/adv→0.3、g/total 翻倍，判别器背完数据集）——
    #      本补丁的梯度裁剪能压制早期尖峰，根治需 train.py 顶部 d_lr_coeff=0.5 + 素材净化
    #      （详见 README 修改详解 #4，未写入默认补丁以免改变大数据集用户的训练动态）。
    # DataLoader num_workers=0 保 Windows spawn + ROCm 稳定性。
    p = "rvc/train/train.py"
    c = read(p)
    if "nan_guard_max_grad_norm" in c:
        print("[8/8] train.py: 训练稳定套装已存在，跳过")
    else:
        backup(p)
        c = replace_checked(
            c,
            "import json",
            "import json\nimport math",
            "train.py import math",
        )
        c = replace_checked(
            c,
            "bf16_adamw = False",
            "bf16_adamw = False\n\n"
            "# NaN/explosion guard: if a backward pass produces non-finite or absurdly large\n"
            "# gradient norms, skip the optimizer step instead of letting Adam poison every\n"
            "# weight in the model (one bad batch used to kill the whole run instantly).\n"
            "nan_guard_max_grad_norm = 1.0e5\n\n"
            "# Gradient clipping caps each optimizer step's magnitude. Stops loss spikes\n"
            "# (e.g. GAN imbalance where the discriminator crushes the generator) from\n"
            "# kicking the model into a bad local minimum. Applied IN-PLACE; the returned\n"
            "# norm is pre-clamp and is what the NaN guard above checks.\n"
            "grad_clip_max_norm = 1.0",
            "train.py NaN-guard 常量",
        )
        c = replace_checked(
            c,
            """                else:
                    loss_disc.backward()
                    grad_norm_d = commons.grad_norm(net_d.parameters())
                    optim_d.step()""",
            """                else:
                    loss_disc.backward()
                    # clip_grad_norm_ caps each step to a safe magnitude and
                    # returns the PRE-clip norm (what the NaN-guard below checks)
                    grad_norm_d = float(
                        torch.nn.utils.clip_grad_norm_(
                            net_d.parameters(), max_norm=grad_clip_max_norm
                        )
                    )
                    if (
                        math.isfinite(grad_norm_d)
                        and grad_norm_d < nan_guard_max_grad_norm
                    ):
                        optim_d.step()
                    else:
                        optim_d.zero_grad()
                        print(
                            f"[NaN-guard] step {global_step}: unsafe D gradients (norm={grad_norm_d}), D update skipped"
                        )
                        grad_norm_d = float("nan")""",
            "train.py D 梯度守卫",
        )
        c = replace_checked(
            c,
            """            else:
                loss_gen_all.backward()
                grad_norm_g = commons.grad_norm(net_g.parameters())
                optim_g.step()""",
            """            else:
                loss_gen_all.backward()
                grad_norm_g = float(
                    torch.nn.utils.clip_grad_norm_(
                        net_g.parameters(), max_norm=grad_clip_max_norm
                    )
                )
                if (
                    math.isfinite(grad_norm_g)
                    and grad_norm_g < nan_guard_max_grad_norm
                ):
                    optim_g.step()
                else:
                    optim_g.zero_grad()
                    print(
                        f"[NaN-guard] step {global_step}: unsafe G gradients (norm={grad_norm_g}), G update skipped"
                    )
                    grad_norm_g = float("nan")""",
            "train.py G 梯度守卫",
        )
        c = replace_checked(
            c,
            """    train_loader = DataLoader(
        train_dataset,
        num_workers=4,
        shuffle=False,
        pin_memory=True,
        collate_fn=collate_fn,
        batch_sampler=train_sampler,
        persistent_workers=True,
        prefetch_factor=8,
    )""",
            """    train_loader = DataLoader(
        train_dataset,
        # num_workers=0 on purpose: Windows spawn + ROCm multiprocessing
        # dataloaders are flaky (proven in the field on Applio-main).
        num_workers=0,
        shuffle=False,
        pin_memory=True,
        collate_fn=collate_fn,
        batch_sampler=train_sampler,
        persistent_workers=False,
        prefetch_factor=None,
    )""",
            "train.py DataLoader num_workers=0",
        )
        write(p, c)
        print("[8/8] train.py: 训练稳定套装(NaN守卫+梯度裁剪+DataLoader单进程)")

    print("\n" + "=" * 50)
    if WARNINGS:
        print("部分补丁未应用，请检查以下问题：")
        for w in WARNINGS:
            print("  - " + w)
        sys.exit(1)
    print("完成! RDNA4 补丁已应用。原文件已备份为 .bak")
    print("\n使用:")
    print("  推理: python applio_cudnn_off.py --open")
    print("  训练: python app.py --open (需设MIOpen环境变量)")


if __name__ == "__main__":
    main()
