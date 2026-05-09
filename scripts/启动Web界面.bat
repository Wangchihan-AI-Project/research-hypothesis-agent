@echo off
cd /d "%~dp0.."
chcp 65001 >nul
echo ====================================
echo   生物医学科研引擎 - Web UI
echo ====================================
echo.
echo 正在启动 Streamlit 服务器...
echo.
py -m streamlit run app.py
pause
