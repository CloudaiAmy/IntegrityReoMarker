@echo off
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements.txt -q
python -m pip install pyinstaller -q

echo.
echo Building PDF Annotation Extractor.exe ...
python -m PyInstaller --noconfirm "PDF Annotation Extractor.spec"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Success! Double-click to run:
echo   dist\PDF Annotation Extractor.exe
echo.
pause
