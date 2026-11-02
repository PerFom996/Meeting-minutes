# -*- coding: utf-8 -*-
"""直接 HTTP 下载 faster-whisper 模型文件，绕过 Xet CAS。"""
import json
import os
import ssl
import urllib.request
from pathlib import Path

MIRROR = "https://hf-mirror.com"
REPO = "Systran/faster-whisper-medium"
CACHE = Path(__file__).resolve().parent / "models"
SNAP_DIR = CACHE / f"models--{REPO.replace('/', '--')}"

# SSL 配置
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def hf_get(path, timeout=30):
    req = urllib.request.Request(
        f"{MIRROR}{path}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return resp.read()


def list_files():
    data = json.loads(hf_get(f"/api/models/{REPO}"))
    return data.get("siblings", [])


def download_file(url, dest):
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  跳过: {dest.name} (已存在)")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  下载: {dest.name} ({url})")
    # Use LFS resolve to get actual URL
    try:
        req = urllib.request.Request(
            f"{MIRROR}/{REPO}/resolve/main/{url}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=300) as resp:
            content = resp.read()
        dest.write_bytes(content)
        print(f"    完成: {len(content) / (1024**2):.1f} MB")
        return True
    except Exception as e:
        print(f"    失败: {e}")
        return False


def main():
    print("=" * 50)
    print("下载 faster-whisper-medium 模型")
    print("=" * 50)

    files = list_files()
    print(f"模型文件列表 ({len(files)} 个):")
    for f in files:
        print(f"  {f['rfilename']} ({f.get('size', '?')} bytes)")

    # Filter to actual model files
    targets = [f for f in files if f["rfilename"] not in (".gitattributes", "README.md")]
    
    blob_dir = SNAP_DIR / "blobs"
    refs_dir = SNAP_DIR / "refs"

    for f in targets:
        fn = f["rfilename"]
        # Get the expected hash (sha256)
        try:
            blob_sha = f.get("lfs", {}).get("sha256") or f.get("sha256", "")
            if not blob_sha:
                # Try to get via the raw API
                info = json.loads(hf_get(f"/api/models/{REPO}/blob/main/{fn}"))
                blob_sha = info.get("sha256", "")
        except Exception:
            blob_sha = ""

        if blob_sha and len(blob_sha) == 64:
            dest = blob_dir / blob_sha
            ref_dest = refs_dir / "main" / fn
            ref_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                ref_dest.unlink()
            except OSError:
                pass
            # Download from resolve URL
            success = download_file(fn, dest)
            if success:
                try:
                    ref_dest.symlink_to(dest)
                except OSError:
                    # Fallback: copy
                    import shutil
                    shutil.copy2(dest, ref_dest)
        else:
            ref_dest = refs_dir / "main" / fn
            ref_dest.parent.mkdir(parents=True, exist_ok=True)
            download_file(fn, ref_dest)

    print("\n验证下载...")
    all_ok = True
    for f in targets:
        fn = f["rfilename"]
        check = refs_dir / "main" / fn
        if check.exists() and check.stat().st_size > 100:
            print(f"  [{check.stat().st_size / (1024**2):.1f} MB] {fn}")
        else:
            print(f"  [缺失] {fn}")
            all_ok = False

    if all_ok:
        print("\n模型下载完成!")
    else:
        print("\n部分文件缺失，请重试")


if __name__ == "__main__":
    main()