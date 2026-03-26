@echo off
echo === PressureMat Build ===
echo.

echo [1/3] Installing dependencies...
pip install pyinstaller pyserial websockets pywebview

echo.
echo [2/3] Building single EXE (this takes a minute)...
pyinstaller --clean --noconfirm pressuremat.spec

echo.
echo [3/3] Done!
echo   Output: dist\PressureMat.exe
echo.
pause
