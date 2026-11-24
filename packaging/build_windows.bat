@echo off
rem Build the StaRbuSt Windows app and installer. Double-click this file or run it in a command window.
rem Needs: Python 3.11+ (python.org). For the installer also Inno Setup 6 (jrsoftware.org).
rem (This file is ASCII only on purpose: batch files are read in the system code page.)
setlocal
cd /d "%~dp0\.."
if not exist packaging\build\venv (
    python -m venv packaging\build\venv || goto :error
)
call packaging\build\venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :error
python -m pip install pyinstaller numpy numba plotly nicegui || goto :error
python packaging\build.py || goto :error
echo.
echo Done. See the packaging\dist folder.
pause
exit /b 0
:error
echo.
echo The build failed. Check the messages above.
pause
exit /b 1
