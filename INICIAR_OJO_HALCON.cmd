@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-ojo-halcon.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo No se pudo iniciar Ojo de Halcon. Revisa el mensaje anterior.
  pause
)

exit /b %EXIT_CODE%
