@echo off
setlocal

cd /d "%~dp0"
call "scripts\setup_scengen_from_scratch.bat"

echo.
echo When setup is done, run this next:
echo   ollama pull qwen2.5vl:7b
echo   ollama serve
echo   scripts\start_scengen.bat A34 S8

endlocal
