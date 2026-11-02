# -*- coding: utf-8 -*-
"""尝试多种方式下载 model.bin：直接 URL、LFS smudge、hf-mirror raw"""
import os, sys, ssl, subprocess
from pathlib import Path

MODEL_DIR = Path(r"D:\ytx\workspace\会议意见\会议总结Appv2.0\会议总结App\models\models--Systran--faster-whisper-medium")
os.chdir(str(MODEL_DIR))

# 方法1: git LFS pull 用原始 hf.co 而非 mirror
print("=== Method 1: git lfs pull from hf.co ===")
# Override LFS endpoint
os.environ.pop("HF_ENDPOINT", None)
result = subprocess.run(
    ["git", "config", "lfs.url", "https://huggingface.co/Systran/faster-whisper-medium"],
    capture_output=True, text=True
)
print(result.stdout, result.stderr)

result = subprocess.run(
    ["git", "lfs", "pull"],
    capture_output=True, text=True,
    timeout=120
)
print(result.stdout[-500:] if result.stdout else "")
print(result.stderr[-500:] if result.stderr else "")
print(f"exit: {result.returncode}")