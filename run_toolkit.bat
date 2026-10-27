@echo off
cd /d "%~dp0"
py -c "import PIL" >nul 2>&1
if errorlevel 1 (
  echo Installing Pillow for screen capture...
  py -m pip install --user pillow
)
py "%~dp0runescape_toolkit.py"
if errorlevel 1 (
  echo.
  echo Toolkit failed to start. Please send a screenshot of this window.
  pause
)
