@echo off
echo ========================================
echo Enable Chrome AI - Nuitka Packaging
echo ========================================
echo.

:: Install dependencies including Nuitka
echo [1/2] Installing dependencies...
uv sync --extra dev

:: Build with Nuitka
echo.
echo [2/2] Building with Nuitka...
uv run python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=pyside6 ^
    --include-data-files=README.md=README.md ^
    --windows-icon-from-ico=icon.ico ^
    --output-filename=EnableChromeAI.exe ^
    --output-dir=dist ^
    main_gui.py

echo.
echo ========================================
echo Build complete! Check dist/ folder
echo ========================================
pause
