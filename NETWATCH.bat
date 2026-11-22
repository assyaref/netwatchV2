@echo off
title NETWATCH
REM Semua pengaturan (mode, interface, subnet, password) diatur dari menu SETTINGS di aplikasi.

REM Minta hak Administrator (dibutuhkan untuk capture paket)
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

cd /d "%~dp0"
REM Pakai Python 3.13 bila ada (dibutuhkan pywebview untuk jendela native)
set "PY=python"
py -3.13 -c "import sys" >nul 2>&1 && set "PY=py -3.13"
%PY% -m netwatch
if errorlevel 1 pause
