@echo off
cd /d "%~dp0.."
REM 设置UTF-8编码
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

REM 启动Streamlit
streamlit run app.py --server.port 8501 --server.headless false
