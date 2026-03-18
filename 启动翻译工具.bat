@echo off
chcp 65001 >nul
echo ============================================
echo   RPG游戏翻译工具 - GUI版本
echo ============================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python！请先安装Python 3.7+
    echo.
    pause
    exit /b 1
)

echo Python版本:
python --version
echo.

REM 进入脚本目录
cd /d "%~dp0"

REM 检查依赖
echo 检查依赖...
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 错误: 依赖安装失败！
        pause
        exit /b 1
    )
)

echo.
echo 正在启动GUI界面...
echo.
echo 提示: 如果是首次使用，建议先阅读 README.md
echo.

REM 启动GUI
python gui_launcher.py

if errorlevel 1 (
    echo.
    echo 错误: 启动失败！
    echo.
    echo 请检查:
    echo 1. 依赖是否正确安装: pip install -r requirements.txt
    echo 2. Python版本是否为3.7+
    echo 3. 查看上面的错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo 程序已退出.
echo.
pause
