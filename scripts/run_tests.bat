@echo off
chcp 65001 >nul
echo ========================================
echo 测试 GenAI 架构师
echo ========================================
echo.

cd /d "%~dp0.."
set PYTHONPATH=%CD%

echo [1/3] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo ERROR: Python 未安装或不在 PATH 中
    pause
    exit /b 1
)
echo OK: Python 可用
echo.

echo [2/3] 测试 GenAI 架构师...
python tests\manual\test_genai_expert.py
if errorlevel 1 (
    echo ERROR: GenAI 测试失败
) else (
    echo OK: GenAI 测试通过
)
echo.

echo [3/3] 测试两阶段漏斗搜索...
python tests\manual\test_two_stage_funnel.py
if errorlevel 1 (
    echo ERROR: 漏斗搜索测试失败
) else (
    echo OK: 漏斗搜索测试通过
)
echo.

echo ========================================
echo 所有测试完成!
echo ========================================
pause
