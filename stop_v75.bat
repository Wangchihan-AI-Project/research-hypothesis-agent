@echo off
REM V7.5 凤凰协议停止脚本

echo ========================================
echo 停止 V7.5 凤凰协议...
echo ========================================

REM 停止 Celery Worker
echo [1/2] 停止 Celery Worker...
taskkill /FI "WINDOWTITLE eq Celery Worker V7.5*" /T /F 2>nul

REM 停止 Streamlit
echo [2/2] 停止 Streamlit UI...
taskkill /FI "WINDOWTITLE eq Streamlit V7.5*" /T /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501.*LISTENING"') do taskkill /F /PID %%a 2>nul

echo ========================================
echo V7.5 已停止
echo Redis 仍在运行 (docker stop research_redis 可停止)
echo ========================================
pause
