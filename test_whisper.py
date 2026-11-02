# -*- coding: utf-8 -*-
import traceback, time, sys, os

try:
    import ctranslate2
    print(f"ctranslate2 version: {ctranslate2.__version__}")
except Exception as e:
    print(f"ctranslate2 import error: {e}")

try:
    from faster_whisper import WhisperModel
    model_path = r"D:\ytx\workspace\会议意见\会议总结Appv2.0\会议总结App\models\faster-whisper-medium"
    print(f"Loading from: {model_path}")
    print(f"model.bin exists: {os.path.isfile(os.path.join(model_path, 'model.bin'))}")
    print(f"model.bin size: {os.path.getsize(os.path.join(model_path, 'model.bin'))}")
    sys.stdout.flush()
    
    # Try with cpu_threads=1 to avoid threading issues
    try:
        print("Trying float32 with cpu_threads=1...", end=" ", flush=True)
        model = WhisperModel(model_path, device="cpu", compute_type="float32", cpu_threads=1)
        print("OK!")
    except Exception as e:
        print(f"FAIL: {e}")
    
    # Try int8
    try:
        print("Trying int8 with cpu_threads=1...", end=" ", flush=True)
        model = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=1)
        print("OK!")
    except Exception as e:
        print(f"FAIL: {e}")
        
    # Try int8_float16
    try:
        print("Trying int8_float16 with cpu_threads=1...", end=" ", flush=True)
        model = WhisperModel(model_path, device="cpu", compute_type="int8_float16", cpu_threads=1)
        print("OK!")
    except Exception as e:
        print(f"FAIL: {e}")
                
except Exception:
    traceback.print_exc()