@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py
    if %errorlevel% equ 0 exit /b 0
    echo.
    echo [警告] pythonw 启动失败，正在回退到 python 启动...
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    python main.py
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 程序异常退出，错误码：%errorlevel%
        pause
    )
    exit /b %errorlevel%
)
echo [错误] 未在系统环境变量 PATH 中找到 pythonw 或 python，请确认已安装 Python。
pause
