@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动「会议纪要」…
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0app.py"
) else (
  start "" python "%~dp0app.py"
)
timeout /t 2 >nul
exit
