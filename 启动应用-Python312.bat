@echo off
echo ========================================
echo 使用 Python 3.12 + TensorFlow 启动应用
echo ========================================
echo.

echo 激活 Python 3.12 虚拟环境...
call venv312\Scripts\activate.bat

echo.
echo Python 版本:
python --version

echo.
echo 启动应用...
python movie_recommendation\app.py

pause
