@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"
set "PROJECT_NAME=%~n0"
set "PROJECT_NAME=ScenGen"

echo ============================================================
echo %PROJECT_NAME% setup from scratch for Windows Command Prompt
echo ============================================================
echo.
echo Project folder detected:
echo   %ROOT_DIR%
echo.
echo To run this on any Windows machine:
echo 1. Download or copy the whole project folder.
echo 2. Open Command Prompt.
echo 3. Move into the project folder with:
echo      cd /d path\to\your\%PROJECT_NAME%
echo 4. Run:
echo   scripts\setup_scengen_from_scratch.bat
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3.9"
) else (
    set "PYTHON_CMD=python"
)

echo [1/6] Checking Python...
%PYTHON_CMD% --version
if errorlevel 1 (
    echo.
    echo Python 3.9 was not found.
    echo Install Python 3.9 first, then run this script again.
    exit /b 1
)
echo.

echo [2/6] Creating virtual environment in .\venv ...
if not exist "venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Existing virtual environment found. Reusing it.
)
echo.

echo [3/6] Activating virtual environment...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate venv.
    exit /b 1
)
echo.

echo [4/6] Installing requirements from requirements.txt ...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    exit /b 1
)
echo.

echo [5/6] Checking ADB...
where adb >nul 2>nul
if errorlevel 1 (
    echo ADB was not found in PATH.
    echo Install Android platform-tools and make sure adb works in Command Prompt.
    echo Example check:
    echo   adb devices
) else (
    adb version
)
echo.

echo [6/6] Checking Ollama...
where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama was not found in PATH.
    echo Install Ollama, then run these commands:
    echo   ollama pull qwen2.5vl:7b
    echo   ollama serve
) else (
    ollama --version
    ollama list | findstr /i /c:"qwen2.5vl:7b" >nul
    if errorlevel 1 (
        echo Model qwen2.5vl:7b is not installed yet.
        echo Run:
        echo   ollama pull qwen2.5vl:7b
    ) else (
        echo Model qwen2.5vl:7b is available.
    )
)
echo.

echo Final run checklist
echo 1. Make sure Ollama is running and qwen2.5vl:7b is installed:
echo      ollama pull qwen2.5vl:7b
echo      ollama serve
echo.
echo 2. Connect your Android device and verify it is visible:
echo      adb devices
echo.
echo 3. Start %PROJECT_NAME% with an app ID and scenario ID:
echo      python test.py A34 S8
echo.
echo 4. Or use the helper run script:
echo      scripts\start_scengen.bat A34 S8
echo.
echo 5. If you cloned this project into a different folder name, that is fine.
echo    These scripts always use the folder they are currently inside.
echo.
echo Example IDs already present in testbot\conf.json:
echo   App A34 = Calculator-2
echo   Scenario S8 = calculation (8+5)
echo.
echo Setup script complete.

endlocal
