@echo off
echo === PressureMat Build ===
pip install pyinstaller
pyinstaller --onefile --noconsole ^
    --name PressureMat ^
    --icon assets\icon.ico ^
    --add-data "app.html;." ^
    --add-data "assets;assets" ^
    main.py
echo.
echo Build complete: dist\PressureMat.exe
pause
