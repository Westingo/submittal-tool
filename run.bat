@echo off
rem ===================================================================
rem  Metro Access Control - Submittal Builder
rem  Double-click this file to start the app. First run sets things up
rem  (about a minute); after that it opens in its own window in seconds.
rem  Close the app window (or double-click stop.bat) to shut it down.
rem ===================================================================
setlocal
cd /d "%~dp0"
title Metro Submittal Builder

rem --- locate Python -------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo   Python is not installed on this computer.
  echo.
  echo   1. Get Python 3.12 from  https://www.python.org/downloads/
  echo   2. During setup, TICK the box "Add python.exe to PATH"
  echo   3. Then double-click run.bat again.
  echo.
  pause
  exit /b 1
)

rem --- create the private environment on first run -------------------
if not exist ".venv\Scripts\python.exe" (
  echo Setting up for the first time - creating environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo   Could not create the environment. Is Python installed correctly?
    pause
    exit /b 1
  )
)
set "VENV_PY=.venv\Scripts\python.exe"
set "VENV_PYW=.venv\Scripts\pythonw.exe"

rem --- install dependencies on first run -----------------------------
if not exist ".venv\.deps-installed" (
  echo Installing components - this only happens once, about a minute...
  "%VENV_PY%" -m pip install --upgrade pip -q
  "%VENV_PY%" -m pip install -r requirements.txt -q
  if errorlevel 1 (
    echo.
    echo   Component install failed - check your internet connection
    echo   and run this again.
    pause
    exit /b 1
  )
  echo installed> ".venv\.deps-installed"
)

rem --- launch the desktop window (pythonw = no console) and exit ------
rem  The app opens in its own window; this console closes itself.
echo.
echo   Opening Metro Submittal Builder...
start "" "%VENV_PYW%" desktop.py

endlocal
