@echo off
echo === PressureMat Build ===
echo.

echo [1/3] Installing dependencies...
pip install pyinstaller pyserial websockets pywebview

echo.
echo [2/3] Building with PyInstaller (onedir)...
pyinstaller --clean --noconfirm pressuremat.spec

echo.
echo [3/3] Build complete!
echo   Output: dist\PressureMat\PressureMat.exe
echo.
echo To create installer, open installer.iss with Inno Setup Compiler.
pause
