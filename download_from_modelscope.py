# -*- coding: utf-8 -*-
"""从 ModelScope 直接下载 faster-whisper-medium 模型文件（纯 HTTP，绕过 Xet/PyTorch）。"""
import json
import os
import ssl
import urllib.request
from pathlib import Path
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = Path(r"D:\ytx\workspace\会议意见\会议总结Appv2.0\会议总结App")
TARGET = BASE / "models" / "faster-whisper-medium"
LOG = BASE / "download_log.txt"


def http_get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read())


def http_download(url, dest_path, timeout=600):
    if dest_path.exists() and dest_path.stat().st_size > 100:
        sz = dest_path.stat().st_size
        print(f"    skip: {dest_path.name} ({sz/(1024**2):.1f} MB)")
        return sz
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            data = resp.read()
        dest_path.write_bytes(data)
        print(f"    done: {dest_path.name} ({len(data)/(1024**2):.1f} MB)")
        return len(data)
    except Exception as e:
        print(f"    FAIL: {dest_path.name}: {e}")
        return 0


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---- Step 1: find the model on ModelScope ----
log("Searching ModelScope for faster-whisper-medium...")
search = http_get_json(
    "https://modelscope.cn/api/v1/search/models?query=faster-whisper-medium&page=1&page_size=10"
)
models = search.get("Data", {}).get("Models", [])
if not models:
    log("No results. Trying broader search...")
    search = http_get_json(
        "https://modelscope.cn/api/v1/search/models?query=faster-whisper&page=1&page_size=20"
    )
    models = search.get("Data", {}).get("Models", [])
    log(f"Found {len(models)} models")

found = False
for m in models:
    name = m.get("Name", "")
    mid = m.get("Id", "")
    log(f"  {name} (id={mid})")
    if "faster-whisper" in name.lower() and "medium" in name.lower():
        log(f"  ==> MATCH: {mid}")
        model_id = mid
        found = True
        break

if not found and models:
    # Try first one that has faster-whisper
    for m in models:
        name = m.get("Name", "")
        if "faster-whisper" in name.lower():
            log(f"  Using: {m.get('Id')}")
            model_id = m["Id"]
            found = True
            break

if not found:
    log("FAIL: could not find faster-whisper-medium on ModelScope")
    # Try a direct known URL
    model_id = "keepitsimple/faster-whisper-medium"
    log(f"Trying known ID: {model_id}")

# ---- Step 2: get file list ----
log(f"Getting files for: {model_id}")
# ModelScope file list API
info_url = f"https://modelscope.cn/api/v1/models/{model_id}/repo/files?Revision=master&Recursive=true"
try:
    info = http_get_json(info_url)
    files = info.get("Data", {}).get("Files", [])
    log(f"Found {len(files)} files")
    for f in files:
        name = f.get("Name", "?")
        size = f.get("Size", 0)
        log(f"  {name}: {size} bytes")
except Exception as e:
    log(f"API error: {e}")
    # Hardcode known files for faster-whisper-medium
    files = [
        {"Name": "config.json", "Size": 2480},
        {"Name": "tokenizer.json", "Size": 2304580},
        {"Name": "vocabulary.txt", "Size": 511726},
        {"Name": "model.bin", "Size": 1527906378},
    ]

# ---- Step 3: download each file ----
TARGET.mkdir(parents=True, exist_ok=True)

for f in files:
    name = f.get("Name", "")
    size = f.get("Size", 0)
    dest = TARGET / name
    log(f"Downloading {name} ({size/(1024**2):.1f} MB)...")
    
    # ModelScope source download URL
    url = f"https://modelscope.cn/api/v1/models/{model_id}/repo?Revision=master&FilePath={name}"
    http_download(url, dest)
    
    # If empty/404, try alternate URL pattern
    if not dest.exists() or dest.stat().st_size < 100:
        url2 = f"https://www.modelscope.cn/models/{model_id}/resolve/master/{name}"
        log(f"  Retry: {url2}")
        http_download(url2, dest)

# ---- Step 4: verify ----
log("\nFinal check:")
for f in files:
    name = f.get("Name", "")
    dest = TARGET / name
    if dest.exists():
        log(f"  [OK] {name}: {dest.stat().st_size/(1024**2):.1f} MB")
    else:
        log(f"  [MISSING] {name}")

log(f"\nModel path: {TARGET}")
log("Done!")