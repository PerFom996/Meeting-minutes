# -*- coding: utf-8 -*-
"""直接从 ModelScope 下载 faster-whisper 模型（绕过 Xet、绕过 PyTorch 导入）。"""
import os
import ssl
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
CACHE = BASE / "models"
TARGET = CACHE / "faster-whisper-medium"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

FILES = {
    "config.json": "https://www.modelscope.cn/api/v1/models/keepitsimple/faster-whisper-medium/repo?Revision=master&FilePath=config.json",
    "tokenizer.json": "https://www.modelscope.cn/api/v1/models/keepitsimple/faster-whisper-medium/repo?Revision=master&FilePath=tokenizer.json",
    "vocabulary.txt": "https://www.modelscope.cn/api/v1/models/keepitsimple/faster-whisper-medium/repo?Revision=master&FilePath=vocabulary.txt",
    "model.bin": "https://www.modelscope.cn/api/v1/models/keepitsimple/faster-whisper-medium/repo?Revision=master&FilePath=model.bin",
}


def download(url, dest, desc=""):
    if dest.exists() and dest.stat().st_size > 100:
        print(f"  [已存在] {dest.name} ({dest.stat().st_size / (1024**2):.1f} MB)")
        return True
    print(f"  [下载中] {desc or dest.name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=600) as resp:
            data = resp.read()
        dest.write_bytes(data)
        print(f"  [完成] {len(data) / (1024**2):.1f} MB")
        return True
    except Exception as e:
        print(f"  [失败] {e}")
        return False


TARGET.mkdir(parents=True, exist_ok=True)
for fn, url in FILES.items():
    download(url, TARGET / fn, fn)

print(f"\n模型文件已保存到: {TARGET}")
print("请手动创建指向 faster-whisper 期望路径的符号链接或复制。")