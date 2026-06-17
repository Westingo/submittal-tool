@echo off
rem  Stops the Submittal Builder (frees port 8484). You can also just
rem  close the run.bat window.
setlocal
set "found="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8484" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%a >nul 2>&1 && set "found=1"
)
if defined found (
  echo Submittal Builder stopped.
) else (
  echo Submittal Builder was not running.
)
ping -n 3 127.0.0.1 >nul
endlocal
