@echo off
chcp 65001 >nul
set PYTHON_HARNESS=C:\Users\lkj\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
cd /d "%~dp0"
echo 启动会议总结App (Python 3.12 + faster-whisper)...
"%PYTHON_HARNESS%" app.py
pause