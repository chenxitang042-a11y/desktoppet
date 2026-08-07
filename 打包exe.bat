@echo off
chcp 65001 >nul
REM 把桌宠打包成一个单独的 DesktopPet.exe,方便发给别人。
REM 在 Windows 上双击运行本文件即可。产物在 dist\ 文件夹里。

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 没有找到 Python。请先安装 Python(勾选 Add Python to PATH)。
    pause
    exit /b 1
)

echo ==^> 安装/检查依赖...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo ==^> 开始打包(第一次会比较慢,请耐心等)...
REM --windowed  不弹黑色命令行窗口
REM --onefile   打成单个 exe
REM --add-data  把美术素材一起塞进 exe(Windows 用分号分隔)
python -m PyInstaller --noconfirm --clean ^
    --name DesktopPet ^
    --windowed ^
    --onefile ^
    --add-data "assets;assets" ^
    pet.py

echo.
if exist "dist\DesktopPet.exe" (
    echo ==^> 完成!
    echo     exe 在这里:  dist\DesktopPet.exe
    echo     双击它就能跑,也可以直接发给别人。
) else (
    echo !! 打包好像失败了,往上翻看看红色报错。
)
pause
