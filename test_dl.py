# -*- coding: utf-8 -*-
"""尝试直接从 HF mirror 下载模型文件（不走 Xet CAS）。"""
import os, ssl, urllib.request
from pathlib import Path

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CACHE = Path(r"D:\ytx\workspace\会议意见\会议总结Appv2.0\会议总结App\models")
SNAP = CACHE / "models--Systran--faster-whisper-medium"
SNAP.mkdir(parents=True, exist_ok=True)
BLOBS = SNAP / "blobs"
BLOBS.mkdir(parents=True, exist_ok=True)
REFS = SNAP / "refs" / "main"
REFS.mkdir(parents=True, exist_ok=True)

# SHA256 of model.bin from the HF API
MODEL_SHA = "4f4fbde9ef3dc7957f5a4474dd7399bf1d4f87ff951e6e4ce5c366d2ad91f427"

# Try multiple download approaches
HAS_SHA = os.environ.get("HF_HUB_DISABLE_XET", "0") == "1"
URLS = []

if HAS_SHA:
    # Direct blob URL via hf-mirror (might still use Xet)
    URLS.append(f"https://hf-mirror.com/Systran/faster-whisper-medium/resolve/main/model.bin")

# Regular download    
URLS.append(f"https://hf-mirror.com/Systran/faster-whisper-medium/resolve/main/model.bin?download=1")

for url in URLS:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            print(f"Final URL: {r.geturl()[:150]}...")
            ct = r.info().get("Content-Type", "?")
            cl = r.info().get("Content-Length", "?")
            print(f"Content-Type: {ct}, Content-Length: {cl}")
            if "json" in ct:
                data = r.read().decode()
                print(f"Response: {data[:500]}")
            else:
                print("Got binary response - might be the actual model!")
    except Exception as e:
        print(f"URL {url[:80]}... -> {e}")
    print()