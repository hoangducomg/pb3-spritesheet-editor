@echo off
setlocal EnableExtensions
title Plazma Burst 3 Animate Frames Editor - Setup and Run
cd /d "%~dp0"

set "APP=PB3 Animate Frames Editor.py"
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"

echo ==========================================
echo  Plazma Burst 3 Animate Frames Editor
echo  Setup and launch
echo ==========================================
echo.

REM ---- 1. Check the app file ----
if not exist "%APP%" (
    echo [ERROR] "%APP%" was not found in this folder:
    echo         %~dp0
    echo Put setup.bat in the same folder as the app file.
    goto :fail
)

REM ---- 2. Find Python 3 ----
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PY=python"
    )
)
if not defined PY (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH" during install, then run this file again.
    goto :fail
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.9 or newer is required.
    %PY% --version
    goto :fail
)
echo Using Python:
%PY% --version
echo.

REM ---- 3. Create or repair the virtual environment ----
REM A .venv copied from another computer (or left half-installed) has a broken pip.
REM If pip does not run inside it, delete it and build a clean one.
set "NEED_VENV=0"
if not exist "%VENV_PY%" set "NEED_VENV=1"
if exist "%VENV_PY%" (
    "%VENV_PY%" -m pip --version >nul 2>nul
    if errorlevel 1 set "NEED_VENV=1"
)

if "%NEED_VENV%"=="1" (
    echo Creating a clean virtual environment in .venv ...
    if exist "%VENV_DIR%" (
        rmdir /s /q "%VENV_DIR%" >nul 2>nul
        if exist "%VENV_DIR%" (
            echo [ERROR] Could not delete the old .venv folder. Close any program using it and try again.
            goto :fail
        )
    )
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :fail
    )
)

REM ---- 4. Install dependencies ----
echo.
echo Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 goto :pip_fail

echo.
echo Installing Pillow (required) ...
"%VENV_PY%" -m pip install --upgrade pillow --disable-pip-version-check
if errorlevel 1 goto :pip_fail

echo.
echo Installing OpenCV (needed only for video input) ...
"%VENV_PY%" -m pip install --upgrade opencv-python --disable-pip-version-check
if errorlevel 1 (
    echo [WARNING] OpenCV could not be installed. The app will run, but video input will be disabled.
)

REM ---- 5. Verify the install ----
echo.
echo Checking installed packages ...
"%VENV_PY%" -c "import tkinter, PIL; print('  tkinter OK'); print('  Pillow', PIL.__version__, 'OK')"
if errorlevel 1 (
    echo [ERROR] Pillow or tkinter failed to load.
    echo If tkinter is the problem, reinstall Python and tick "tcl/tk and IDLE".
    goto :fail
)
"%VENV_PY%" -c "import cv2; print('  OpenCV', cv2.__version__, 'OK')" >nul 2>nul
if errorlevel 1 (
    echo   OpenCV not available (video input disabled).
)

REM ---- 6. Launch the app (no console window) ----
echo.
echo Starting the editor ...
if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" "%APP%"
) else (
    start "" "%VENV_PY%" "%APP%"
)
endlocal
exit /b 0

:pip_fail
echo [ERROR] Package installation failed.
echo Check your internet connection, then run this file again.
goto :fail

:fail
echo.
echo Setup did not finish. Read the message above.
pause
endlocal
exit /b 1