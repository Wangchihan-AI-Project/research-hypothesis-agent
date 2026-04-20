@echo off
REM 设置UTF-8编码
chcp 65001 >/dev/null 2>&1
set PYTHONIOENCODING=utf-8

REM 启动Streamlit
streamlit run app_v7.py --server.port 8501 --server.headless false
