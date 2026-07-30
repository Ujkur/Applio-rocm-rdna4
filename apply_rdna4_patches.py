#!/usr/bin/env python3
"""Applio RDNA4 (gfx1201) 补丁脚本
在原版 Applio 根目录运行: python apply_rdna4_patches.py
自动应用所有 RDNA4 优化修改。修改前自动备份原文件。
"""
import os, sys, re, json, shutil

def backup(path):
    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

def main():
    if not os.path.isfile("app.py") or not os.path.isdir("rvc"):
        print("错误: 请在 Applio 根目录运行此脚本（需有 app.py 和 rvc/）")
        sys.exit(1)

    print("Applio RDNA4 (gfx1201) 补丁脚本")
    print("=" * 50)

    # 1. config.py: x_center=5
    p = "rvc/configs/config.py"
    backup(p)
    with open(p, "r", encoding="utf-8") as f:
        c = f.read()
    c = re.sub(
        r'x_pad, x_query, x_center, x_max = \([^)]+\)',
        'x_pad, x_query, x_center, x_max = (1, 3, 5, 6)',
        c
    )
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("[1/5] config.py: x_center=5 (抗金属破音, 实际NSF前向~7s<临界7-8s)")

    # 2. pipeline.py: crossfade + faiss中文路径 + import
    p = "rvc/infer/pipeline.py"
    backup(p)
    with open(p, "r", encoding="utf-8") as f:
        c = f.read()
    if "import tempfile" not in c:
        c = c.replace("import sys\nimport torch", "import sys\nimport shutil\nimport tempfile\nimport torch")
    old_concat = "        audio_opt = np.concatenate(audio_opt)"
    new_crossfade = '''        # RDNA4: 等功率crossfade(4096/85ms) 替代裸concatenate
        if len(audio_opt) > 1:
            min_chunk_len = min(len(c) for c in audio_opt)
            fade_len = min(4096, min_chunk_len // 3)
            if fade_len >= 2:
                result = audio_opt[0].copy()
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
            audio_opt = audio_opt[0]'''
    c = c.replace(old_concat, new_crossfade)
    old_faiss = "                index = faiss.read_index(file_index)\n                big_npy = index.reconstruct_n"
    new_faiss = '''                try:
                    file_index.encode("ascii")
                except UnicodeEncodeError:
                    tmp_dir = tempfile.mkdtemp(prefix="faiss_")
                    ascii_path = os.path.join(tmp_dir, "index")
                    shutil.copy2(file_index, ascii_path)
                    index = faiss.read_index(ascii_path)
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                else:
                    index = faiss.read_index(file_index)
                big_npy = index.reconstruct_n'''
    c = c.replace(old_faiss, new_faiss)
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("[2/5] pipeline.py: crossfade(4096等功率) + faiss中文路径 + import")

    # 3. train.py: benchmark + distributed
    p = "rvc/train/train.py"
    backup(p)
    with open(p, "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("torch.backends.cudnn.benchmark = True", "torch.backends.cudnn.benchmark = False")
    c = re.sub(
        r'(\s+)dist\.init_process_group\(',
        r'\1if hasattr(dist, "init_process_group") and n_gpus > 1 and device.type == "cuda":\n\1    dist.init_process_group(',
        c
    )
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("[3/5] train.py: benchmark=False + distributed条件(单GPU跳过)")

    # 4. config_template.json: bf16
    p = "assets/config_template.json"
    backup(p)
    with open(p, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["precision"] = "bf16"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print("[4/5] config_template.json: precision=bf16")

    # 5. applio_cudnn_off.py
    if os.path.isfile("applio_cudnn_off.py"):
        print("[5/5] applio_cudnn_off.py: 已存在")
    else:
        print("[5/5] 警告: applio_cudnn_off.py 不在当前目录，请从本repo复制")

    print("\n" + "=" * 50)
    print("完成! RDNA4 补丁已应用。原文件已备份为 .bak")
    print("\n使用:")
    print("  推理: python applio_cudnn_off.py --open")
    print("  训练: python app.py --open (需设MIOpen环境变量)")

if __name__ == "__main__":
    main()
