@echo off
chcp 65001 >nul
echo ========================================
echo YOLO 一键部署工具 - 打包脚本
echo ========================================
echo.

set "VENV_DIR=%~dp0venv"
set "PYINSTALLER=%VENV_DIR%\Scripts\pyinstaller.exe"
set "SCRIPT=%~dp0main.py"
set "OUTPUT_DIR=%~dp0dist"

if not exist "%PYINSTALLER%" (
    echo [错误] 未找到 pyinstaller，请先确保虚拟环境已创建并安装依赖
    pause
    exit /b 1
)

echo [信息] 清理旧的打包文件...
if exist "%OUTPUT_DIR%" (
    rmdir /s /q "%OUTPUT_DIR%"
)
if exist "%~dp0build" (
    rmdir /s /q "%~dp0build"
)
if exist "%~dp0main.spec" (
    del /q "%~dp0main.spec"
)

echo [信息] 开始打包...
"%PYINSTALLER%" ^
    --onefile ^
    --windowed ^
    --name "YOLO_AutoInstaller" ^
    --icon "%~dp0assets\app.ico" ^
    --add-data "%~dp0repos.yaml;." ^
    --add-data "%~dp0assets;assets" ^
    --clean ^
    "%SCRIPT%"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo [成功] 打包完成！
    echo 输出文件: %OUTPUT_DIR%\YOLO_AutoInstaller.exe
    echo ========================================
    echo.
    echo 注意: 请确保 repos.yaml 与 exe 在同一目录下
) else (
    echo.
    echo [失败] 打包失败，请查看上方错误信息
)

pause
