# -*- coding: utf-8 -*-
"""Applio WebUI 启动 wrapper：先禁用 cudnn(MIOpen) 卷积，再启动 app.py。
用途：推理场景规避 gfx1201 上 MIOpen find-db 写入崩溃，并显著提速。
注意：训练请仍用原 start-Applio.bat（训练 shape 固定，MIOpen find 可摊销，原生卷积反而慢）。

健壮性说明：
- 用绝对路径定位 app.py 并把脚本目录注入 sys.path，从任意工作目录运行均可。
- cudnn 关闭在模块级执行：multiprocessing spawn 子进程 re-import 本模块时同样生效。
- 主逻辑置于 if __name__ == "__main__" 守卫内，避免 spawn 子进程递归启动 app.py。
"""
import os
import runpy
import sys

import torch

# 模块级设置：spawn 子进程 re-import 本文件时也会执行到这里
torch.backends.cudnn.enabled = False
os.environ["APPLIO_CUDNN_OFF"] = "1"


def main():
    print("[applio_cudnn_off] torch.backends.cudnn.enabled = False (MIOpen conv bypassed)")

    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    app_path = os.path.join(app_dir, "app.py")
    if not os.path.isfile(app_path):
        print(f"[applio_cudnn_off] 错误: 未找到 {app_path}，请将本脚本放在 Applio 根目录")
        sys.exit(1)

    sys.argv = ["app.py"] + sys.argv[1:]
    runpy.run_path(app_path, run_name="__main__")


if __name__ == "__main__":
    main()
