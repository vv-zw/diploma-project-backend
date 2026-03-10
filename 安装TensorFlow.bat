@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_ACTIVATE=%ROOT%venv312\Scripts\activate.bat"
set "REQ_FILE=%ROOT%requirements.txt"

echo ========================================
echo Install TensorFlow into Python 3.12 env
echo ========================================
echo.

if not exist "%VENV_ACTIVATE%" (
    echo ERROR: venv activate script not found:
    echo   "%VENV_ACTIVATE%"
    pause
    exit /b 1
)

if not exist "%REQ_FILE%" (
    echo ERROR: requirements file not found:
    echo   "%REQ_FILE%"
    pause
    exit /b 1
)

echo [1/6] Activate Python 3.12 virtual env...
call "%VENV_ACTIVATE%"
if errorlevel 1 (
    echo ERROR: failed to activate venv312.
    pause
    exit /b 1
)

echo.
echo [2/6] Check Python version...
python --version
echo.

echo [3/6] Upgrade pip...
python -m pip install --upgrade pip
echo.

echo [4/6] Install project dependencies...
pip install -r "%REQ_FILE%"
echo.

echo [5/6] Install TensorFlow (Tsinghua mirror)...
pip install tensorflow -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.

echo [6/6] Verify TensorFlow install...
python -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__)"
echo.

echo ========================================
echo Install finished.
echo ========================================
echo.
echo You can run:
echo   python "%ROOT%movie_recommendation\app.py"
echo.
pause
