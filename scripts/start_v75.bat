@echo off
REM V7.5 凤凰协议一键启动脚本

echo ========================================
echo V7.5 凤凰协议启动中...
echo ========================================

REM 1. 启动 Redis
echo [1/3] 启动 Redis...
docker start research_redis 2>nul || docker start redis 2>nul || echo Redis 未运行，请先启动 docker-compose up -d
timeout /t 2 /nobreak >nul

REM 2. 启动 Celery Worker
echo [2/3] 启动 Celery Worker V7.5...
set PROJECT_ROOT=%~dp0..
start "Celery Worker V7.5" cmd /k "cd /d %PROJECT_ROOT% && python -m celery -A src.core.celery_tasks_v75 worker --loglevel=info --pool=solo -n v75-worker@%%h"
timeout /t 3 /nobreak >nul

REM 3. 启动 Streamlit
echo [3/3] 启动 Streamlit UI...
start "Streamlit V7.5" cmd /k "cd /d %PROJECT_ROOT% && python -m streamlit run app.py --server.port 8501"
timeout /t 3 /nobreak >nul

echo ========================================
echo V7.5 启动完成!
echo Redis: redis://localhost:6379
echo Celery Worker: 运行中
echo Streamlit UI: http://localhost:8501
echo ========================================
pause
