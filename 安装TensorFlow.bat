@echo off
echo ========================================
echo 安装 TensorFlow 到 Python 3.12 环境
echo ========================================
echo.

echo [1/6] 激活 Python 3.12 虚拟环境...
call venv312\Scripts\activate.bat
if errorlevel 1 (
    echo 错误: 无法激活虚拟环境
    pause
    exit /b 1
)

echo.
echo [2/6] 检查 Python 版本...
python --version
echo.

echo [3/6] 升级 pip...
python -m pip install --upgrade pip
echo.

echo [4/6] 安装项目依赖...
pip install -r requirements-minimal.txt
echo.

echo [5/6] 安装 TensorFlow（使用国内镜像）...
pip install tensorflow -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.

echo [6/6] 验证 TensorFlow 安装...
python -c "import tensorflow as tf; print('✅ TensorFlow 版本:', tf.__version__)"
echo.

echo ========================================
echo ✅ 安装完成！
echo ========================================
echo.
echo 现在可以运行应用了:
echo   python movie_recommendation\app.py
echo.
pause
