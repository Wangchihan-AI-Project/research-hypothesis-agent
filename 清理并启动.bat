@echo off
REM 完全清理并重启系统

echo ====================================
echo   系统清理和重��
echo ====================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

echo [1/4] 清理Python缓存...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc >nul 2>&1
echo [OK] 缓存已清理

echo.
echo [2/4] 清理旧的日志...
if exist logs\*.log del /q logs\*.log
echo [OK] 日志已清理

echo.
echo [3/4] 验证Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Python
    pause
    exit /b 1
)
echo [OK] Python已安装

echo.
echo [4/4] 启动系统...
echo.
python main.py

REM 如果程序异常退出，暂停以查看错误
if errorlevel 1 (
    echo.
    echo [ERROR] 系统异常退出
    pause
)