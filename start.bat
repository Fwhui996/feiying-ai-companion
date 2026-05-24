@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 🎭 启动 NLP MMD Controller...
echo.

REM 释放旧端口
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8887.*LISTENING" 2^>nul') do (
    echo 关闭旧进程 PID=%%a
    taskkill /PID %%a /F >nul 2>nul
)
timeout /t 1 /nobreak >nul

echo 启动服务器...
start "绯英-MMD-Server" cmd /k "cd /d %~dp0 && echo === 绯英 Server === && python server_nlp.py 8887"

timeout /t 3 /nobreak >nul
start http://localhost:8887/nlp-controller/
echo ✅ 浏览器已打开！
pause
