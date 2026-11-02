# -*- coding: utf-8 -*-
"""会议总结 App —— 本地离线引擎一键安装脚本（faster-whisper）"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WHISPER_CACHE = BASE_DIR / "models"

MODEL = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "medium"
CHECK_ONLY = "--check" in sys.argv


def check_python():
    print(f"Python: {sys.version}")
    print(f"目录: {BASE_DIR}")


def check_cuda():
    try:
        import subprocess as sp
        r = sp.run(["nvidia-smi"], capture_output=True, timeout=10)
        if r.returncode == 0:
            print("\n[GPU] NVIDIA 显卡可用，可在 .env 中设置 WHISPER_DEVICE=cuda 加速")
            return True
    except Exception:
        pass
    print("\n[GPU] 未检测到 NVIDIA 显卡，使用 CPU 推理")
    return False


def check_model(model_name):
    model_dir = WHISPER_CACHE / f"faster-whisper-{model_name}"
    if model_dir.exists():
        files = list(model_dir.glob("**/*"))
        total = sum(f.stat().st_size for f in files if f.is_file())
        print(f"\n[模型] {model_name} 已下载 ({total/(1024**3):.2f} GB)")
        print(f"  路径: {model_dir}")
        return True
    print(f"\n[模型] {model_name} 尚未下载")
    return False


def download_model(model_name):
    print("\n" + "=" * 50)
    print(f"下载 Whisper 模型: {model_name}")
    print("=" * 50)

    # 国内优先使用 HF 镜像
    mirrors = [
        "https://hf-mirror.com",
        "https://huggingface.co",
    ]
    for mirror in mirrors:
        os.environ["HF_ENDPOINT"] = mirror
        print(f"\n使用镜像: {mirror}")
        print(f"保存到: {WHISPER_CACHE}")
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                 download_root=str(WHISPER_CACHE))
            print(f"\n[OK] 模型 {model_name} 下载完成！")
            return True
        except Exception as e:
            print(f"镜像 {mirror} 失败: {e}")
            continue
    print("\n[FAIL] 所有镜像均失败，请检查网络或手动下载模型")
    return False


def verify(model_name):
    print("\n" + "=" * 50)
    print("验证模型 ...")
    print("=" * 50)
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_name, device="cpu", compute_type="int8",
                             download_root=str(WHISPER_CACHE))
        import numpy as np
        audio = np.zeros(16000, dtype=np.float32)
        segments, info = model.transcribe(audio, language="zh")
        print(f"  检测语言: {info.language} (概率: {info.language_probability:.2%})")
        print(f"✓ 模型验证通过！")
        return True
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        return False


def summary(model_name):
    sizes = {"tiny": "150MB", "base": "300MB", "small": "950MB", "medium": "1.5GB", "large-v3": "3GB"}
    print("\n" + "=" * 50)
    print("安装完成！")
    print("=" * 50)
    print(f"""
使用说明：
  1. 启动: python app.py
  2. 切换到「录音转写」→ 开始录音 → 停止 → 自动转写
  3. 点击「文字纠错」→「生成纪要」

模型: {model_name} ({sizes.get(model_name, '?')})
位置: {WHISPER_CACHE}
""")


def main():
    check_python()
    check_cuda()

    if CHECK_ONLY:
        try:
            import faster_whisper
            print("\n[faster-whisper] 已安装")
        except ImportError:
            print("\n[faster-whisper] 未安装！pip install faster-whisper")
        check_model(MODEL)
        return

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("\n✗ 请先安装: pip install faster-whisper")
        sys.exit(1)

    if not check_model(MODEL):
        if not download_model(MODEL):
            sys.exit(1)

    verify(MODEL)
    summary(MODEL)


if __name__ == "__main__":
    main()