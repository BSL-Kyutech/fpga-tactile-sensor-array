@echo off
rem Short launcher (put this folder on PATH to type "viz hand" anywhere):
rem   viz graph ^| viz hand ^| viz raw ^| viz calib ^| viz gain ^| viz check ^| viz stop ^| viz status ^| viz restart hand
setlocal
set "A=%~1"
if "%A%"=="" set "A=status"
if /i "%A%"=="graph"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start graph   & goto :eof
if /i "%A%"=="hand"    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start hand    & goto :eof
if /i "%A%"=="raw"     powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start handraw & goto :eof
if /i "%A%"=="calib"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start calib   & goto :eof
if /i "%A%"=="check"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start check   & goto :eof
if /i "%A%"=="gain"    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start gain    & goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" %*
