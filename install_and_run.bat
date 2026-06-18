@echo off
echo ================================================
echo   WSI Clipper v1.0 - Setup
echo   Built by Scott Kilcoyne
echo ================================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python from https://python.org/downloads
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Python found. Installing dependencies...
echo.
pip install flask flask-cors pillow tifffile numpy imagecodecs zarr openslide-python
echo.
echo ================================================
echo   Setup complete! Starting WSI Clipper...
echo ================================================
echo.
python server.py
pause