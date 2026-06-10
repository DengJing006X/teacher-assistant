@echo off
chcp 65001 >nul
title 老师助手

set "PYTHON_DIR=C:\Users\PC\AppData\Local\Programs\Python\Python312"
set "PATH=%PYTHON_DIR%;%PYTHON_DIR%\Scripts;%PATH%"

:: 国内镜像（加速 AI 模型下载）
set "HF_ENDPOINT=https://hf-mirror.com"

cls
echo ============================================
echo          老师助手 - 启动脚本
echo ============================================
echo.
echo 请选择启动模式：
echo.
echo   1  网页版（推荐）
echo   2  钉钉机器人版
echo.
set /p mode="请输入数字 (1 或 2): "

if "%mode%"=="1" goto web
if "%mode%"=="2" goto dingtalk
echo 输入无效，默认启动网页版

:web
cls
python start_public.py
pause
exit /b

:dingtalk
cls
echo ============================================
echo          钉钉机器人版启动中...
echo ============================================
echo.
python main.py
pause
exit /b
