@echo off
REM Build NETWATCH.exe: single file, own icon, no console window, asks for Administrator.
cd /d "%~dp0"
set "PY=python"
py -3.13 -c "import sys" >nul 2>&1 && set "PY=py -3.13"
%PY% -m pip install --upgrade pyinstaller scapy pywebview || goto :err
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name NETWATCH --icon assets\netwatch.ico ^
  --add-data "netwatch\static;netwatch\static" ^
  --collect-submodules scapy ^
  netwatch_app.py || goto :err
echo.
echo Selesai: dist\NETWATCH.exe
pause
exit /b 0
:err
echo Build gagal.
pause
exit /b 1
