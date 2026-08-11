@echo off
chcp 65001 >nul
title 游戏存档管理工具
cd /d "%~dp0"

echo ============================================
echo   游戏存档管理工具 - 启动中...
echo ============================================

rem 找 Python（优先 venv，其次系统 python）
set VENV=%~dp0venv
if exist "%VENV%\Scripts\python.exe" (
    set PY=%VENV%\Scripts\python.exe
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到 Python，请先安装 Python 3.10 或更高版本：
        echo   https://www.python.org/downloads/
        echo 安装时请勾选 "Add Python to PATH"。
        pause
        exit /b 1
    )
    set PY=python
)

rem 首次运行：创建 venv 并安装依赖
if not exist "%VENV%\Scripts\python.exe" (
    echo [首次运行] 正在创建虚拟环境并安装依赖，请稍候...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
    "%VENV%\Scripts\pip.exe" install -r requirements.txt -q
)

rem 检查依赖是否齐全
"%PY%" -c "import flask, watchdog, psutil, waitress, yaml" >nul 2>nul
if errorlevel 1 (
    echo [提示] 正在安装缺失依赖...
    "%VENV%\Scripts\pip.exe" install -r requirements.txt -q
)

echo 正在启动服务...
echo 启动后请用浏览器访问 http://127.0.0.1:8765
echo 按 Ctrl+C 可退出
"%PY%" app.py
pause
