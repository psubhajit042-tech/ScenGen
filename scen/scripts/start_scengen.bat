@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"
set "PROJECT_NAME=ScenGen"

set "APP_ID=%~1"
set "SCENARIO_ID=%~2"

if "%APP_ID%"=="" set "APP_ID=A34"
if "%SCENARIO_ID%"=="" set "SCENARIO_ID=S8"

echo ============================================================
echo Starting %PROJECT_NAME% from Windows Command Prompt
echo ============================================================
echo Folder   : %ROOT_DIR%
echo App ID   : %APP_ID%
echo Scenario : %SCENARIO_ID%
echo.

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run this first in Command Prompt:
    echo   scripts\setup_scengen_from_scratch.bat
    exit /b 1
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate venv.
    exit /b 1
)

where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama was not found in PATH.
    echo Install Ollama and run:
    echo   ollama pull qwen2.5vl:7b
    echo   ollama serve
    exit /b 1
)

ollama list | findstr /i /c:"qwen2.5vl:7b" >nul
if errorlevel 1 (
    echo Ollama model qwen2.5vl:7b was not found.
    echo Run:
    echo   ollama pull qwen2.5vl:7b
    exit /b 1
)

where adb >nul 2>nul
if errorlevel 1 (
    echo adb was not found in PATH.
    echo Install Android platform-tools and verify:
    echo   adb devices
    exit /b 1
)

echo Checking connected devices...
adb devices
echo.
echo Make sure Ollama is running in the background.
echo If it is not running, start it in another Command Prompt with:
echo   ollama serve
echo.
echo Running:
echo   python test.py %APP_ID% %SCENARIO_ID%
echo.
python test.py %APP_ID% %SCENARIO_ID%

endlocal
