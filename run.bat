@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

set "PROMPTSMITH_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PROMPTSMITH_PYTHON=%CD%\.venv\Scripts\python.exe"
echo [PromptSmith] Starting WebView2 using "%PROMPTSMITH_PYTHON%"
"%PROMPTSMITH_PYTHON%" run_promptsmith.py --renderer web %*
set "PROMPTSMITH_EXIT_CODE=%ERRORLEVEL%"
if "%PROMPTSMITH_EXIT_CODE%"=="0" goto finish

echo.
echo [PromptSmith] Startup failed. See the error above.
echo If Python dependencies are missing, run in the project directory:
echo   "%PROMPTSMITH_PYTHON%" -m pip install -r requirements.txt
echo The Web interface also requires Microsoft Edge WebView2 Runtime.
echo Explicit Tk compatibility mode: run.bat --renderer tk
pause

:finish
popd
exit /b %PROMPTSMITH_EXIT_CODE%
