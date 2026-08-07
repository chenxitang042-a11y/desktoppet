@echo off
chcp 65001 >nul
REM 直接运行桌宠(开发/测试用,不打包)。
REM 第一次运行会自动装依赖。

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 没有找到 Python。
    echo 请先到 https://www.python.org/downloads/ 下载安装,
    echo 安装时记得勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

echo 检查依赖...
python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo 第一次运行,正在安装 PySide6(界面库),请稍等...
    python -m pip install -r requirements.txt
)

echo 启动桌宠...
python pet.py
pause
