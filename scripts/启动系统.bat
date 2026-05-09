@echo off
chcp 65001 >nul
title 研究假设生成系统

echo.
echo ============================================================
echo              研究假设生成系统
echo         基于多智能体协作的科研假设生成工具
echo                 (Claude Opus 4.6 驱动)
echo ============================================================
echo.
echo [信息] 正在启动系统...
echo.

REM 切换到项目根目录
cd /d "%~dp0.."

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
echo [信息] 检查依赖包...
python -c "import anthropic, sqlalchemy, biopython, rich, questionary" >nul 2>&1
if errorlevel 1 (
    echo [警告] 缺少依赖包，正在安装...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM 清理缓存
echo [信息] 清理Python缓存...
if exist __pycache__ rmdir /s /q __pycache__ 2>nul
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc >nul 2>&1

REM 检查配置
echo [信息] 检查配置文件...
if not exist .env (
    echo [错误] 未找到.env配置文件
    pause
    exit /b 1
)

REM 启动系统
echo.
echo ============================================================
echo [信息] 系统启动中...
echo ============================================================
echo.
python main.py

REM 如果程序异常退出
if errorlevel 1 (
    echo.
    echo ============================================================
    echo [错误] 系统异常退出
    echo.
    echo 故障排查：
    echo 1. 检查API密钥是否正确
    echo 2. 检查网络连接
    echo 3. 运行测试: python test_complete.py
    echo ============================================================
    pause
)