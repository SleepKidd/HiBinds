@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title HiBinds EXE Builder

echo ================================================
echo                HiBinds EXE Builder
echo ================================================
echo Project: %CD%
echo.

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo ERROR: Python was not found.
  echo Install Python 3.11+ and run this file again.
  echo.
  pause
  exit /b 1
)

%PY% --version
if errorlevel 1 goto :fail

echo.
echo [1/4] Checking pip...
%PY% -m pip --version
if errorlevel 1 goto :fail

echo.
echo [2/4] Installing build dependencies...
%PY% -m pip install --user --upgrade customtkinter pyinstaller
if errorlevel 1 goto :fail

echo.
echo [3/4] Building one-file EXE...
%PY% build.py
if errorlevel 1 goto :fail

echo.
echo [4/4] Verifying output...
if not exist "%CD%\HiBinds.exe" goto :fail

echo.
echo ================================================
echo BUILD SUCCESS
echo ================================================
echo EXE created:
echo %CD%\HiBinds.exe
echo.
pause
exit /b 0

:fail
echo.
echo ================================================
echo BUILD FAILED
echo ================================================
echo Check the error shown above.
echo.
pause
exit /b 1
