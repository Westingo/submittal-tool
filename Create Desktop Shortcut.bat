@echo off
rem  Puts a "Metro Submittal Builder" icon on your Desktop that launches the
rem  app window directly (no console). Run run.bat once first so the
rem  environment exists.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo.
  echo   Run run.bat once first to set things up, then run this again.
  echo.
  pause
  exit /b 1
)

set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
set "WORKDIR=%~dp0"

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Metro Submittal Builder.lnk'); $s.TargetPath='%TARGET%'; $s.Arguments='desktop.py'; $s.WorkingDirectory='%WORKDIR%'; $s.Save()"

echo.
echo   Created "Metro Submittal Builder" on your Desktop.
echo   Double-click it any time to open the app.
echo.
pause
endlocal
