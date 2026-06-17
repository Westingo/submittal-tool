@echo off
rem ===================================================================
rem  Metro Access Control - Submittal Builder
rem  Double-click this file to start the app. First run sets things up
rem  (about a minute); after that it starts in a few seconds.
rem  Keep the window that opens running while you work.
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

rem --- open the browser a few seconds after the server starts --------
start "" /min cmd /c "ping -n 5 127.0.0.1 >nul & explorer http://localhost:8484"

echo.
echo   ==============================================================
echo     Metro Submittal Builder is starting...
echo     Your browser will open at  http://localhost:8484
echo.
echo     KEEP THIS WINDOW OPEN while you work.
echo     Close it (or double-click stop.bat) to shut the app down.
echo   ==============================================================
echo.
"%VENV_PY%" app.py

endlocal
