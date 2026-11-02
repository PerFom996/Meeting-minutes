# -*- coding: utf-8 -*-
"""会议纪要 · 桌面版入口。

双击运行后用独立窗口打开应用（内嵌本地服务，不依赖浏览器标签页）。
若当前环境缺少图形组件，会自动回退到系统浏览器打开。
"""
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
LOG_FILE = BASE_DIR / "app.log"
APP_PORT = 18765

# 打包成无控制台窗口的 exe 后，标准流为 None，日志库会因此报错
if sys.stdout is None or sys.stderr is None:
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null


def log_error() -> None:
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 启动失败\n")
        fh.write(traceback.format_exc())


def port_in_use(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_ready(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.3):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def window_size() -> tuple[int, int]:
    """按屏幕大小自适应，避免小屏 / 高 DPI 下窗口超出可显示区域。"""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1280, 860
    return min(1280, max(920, width - 200)), min(880, max(620, height - 140))


def main() -> None:
    import uvicorn
    from server import app as fastapi_app

    if port_in_use(APP_PORT):
        print("「会议纪要」已在运行，请查看已打开的窗口")
        return

    port = APP_PORT
    config = uvicorn.Config(
        fastapi_app, host="127.0.0.1", port=port, log_level="warning", log_config=None
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    if not wait_ready(port):
        raise RuntimeError("本地服务启动超时，请查看 app.log")

    url = f"http://127.0.0.1:{port}/"

    try:
        import webview
    except Exception:
        log_error()
        webbrowser.open(url)
        print(f"已用浏览器打开：{url}（关闭此窗口即退出）")
        input()
        server.should_exit = True
        return

    win_width, win_height = window_size()
    webview.create_window(
        "会议纪要",
        url,
        width=win_width,
        height=win_height,
        min_size=(920, 620),
        text_select=True,
        confirm_close=False,
    )
    webview.start(private_mode=False, storage_path=str(BASE_DIR / ".userdata"))
    server.should_exit = True


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error()
        print("启动失败，详情见 app.log")
        sys.exit(1)
