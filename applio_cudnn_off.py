# -*- coding: utf-8 -*-
"""Applio WebUI 启动 wrapper：先禁用 cudnn(MIOpen) 卷积，再启动 app.py。
用途：推理场景规避 gfx1201 上 MIOpen find-db 写入崩溃，并显著提速。
注意：训练请仍用原 start-Applio.bat（训练 shape 固定，MIOpen find 可摊销，原生卷积反而慢）。"""
import runpy
import sys

import torch

torch.backends.cudnn.enabled = False
print("[applio_cudnn_off] torch.backends.cudnn.enabled = False (MIOpen conv bypassed)")

sys.argv = ["app.py"] + sys.argv[1:]
runpy.run_path("app.py", run_name="__main__")
