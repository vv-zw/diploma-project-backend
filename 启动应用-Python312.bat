@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_ACTIVATE=%ROOT%venv312\Scripts\activate.bat"
set "APP_FILE=%ROOT%movie_recommendation\app.py"

echo ========================================
echo Start app with Python 3.12 + TensorFlow
echo ========================================
echo.

if not exist "%VENV_ACTIVATE%" (
    echo ERROR: venv activate script not found:
    echo   "%VENV_ACTIVATE%"
    pause
    exit /b 1
)

if not exist "%APP_FILE%" (
    echo ERROR: app.py not found:
    echo   "%APP_FILE%"
    pause
    exit /b 1
)

echo [1/3] Activate Python 3.12 virtual env...
call "%VENV_ACTIVATE%"
if errorlevel 1 (
    echo ERROR: failed to activate venv312.
    pause
    exit /b 1
)

echo.
echo [2/3] Python version:
python --version

echo.
echo [3/3] Start app...
python "%APP_FILE%"

pause
