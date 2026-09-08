@echo off
chcp 65001 >nul
echo ======================================
echo   课狐 ClassFox Lite - 一键开发模式
echo ======================================
echo.

echo [0/2] 清理旧后端进程...
taskkill /IM class-fox-lite-backend.exe /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ClassAssistant-Backend" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8766 " ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 >nul

echo [1/2] 启动后端服务 (FastAPI)...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Set-Location '%~dp0api-service'; .venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8766 --reload *> '../data/_dev_backend.log'"

echo       等待后端就绪...
timeout /t 4 >nul

echo [2/2] 启动前端 Tauri 开发模式...
cd /d %~dp0app-ui
npm run tauri dev

echo.
echo [清理] 关闭后端服务...
:: 兜底：按端口杀残留进程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8766 " ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
