@echo off
rem Short launcher (put this folder on PATH to type "viz hand" anywhere):
rem   viz graph ^| viz hand ^| viz raw ^| viz calib ^| viz gain ^| viz check ^| viz stop ^| viz status ^| viz restart hand
setlocal
set "A=%~1"
if "%A%"=="" set "A=status"
if /i "%A%"=="graph"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start graph   & goto :eof
if /i "%A%"=="hand"    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start hand    & goto :eof
if /i "%A%"=="zero"    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start zero    & goto :eof
if /i "%A%"=="nocal"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start nocal   & goto :eof
if /i "%A%"=="raw"     powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start handraw & goto :eof
if /i "%A%"=="calib"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start calib   & goto :eof
if /i "%A%"=="check"   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start check   & goto :eof
if /i "%A%"=="gain"    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" start gain    & goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vizctl.ps1" %*
goto :eof

:help
echo viz - start/stop the tactile sensor viewers ^(Icepi Zero, COM port is found automatically^)
echo.
echo   viz graph          line graph of all 24 channels ^(Visualizer\icepizeroo.py^)
echo   viz hand           hand heatmap, force-scale gains applied
echo   viz raw            hand heatmap without force-scale gains ^(zero calibration kept^)
echo   viz nocal          hand heatmap without any calibration ^(no gains, no zero^)
echo   viz zero           hand heatmap + zero calibration at start ^(hands off 4 s^)
echo   viz calib          re-measure which channel each electrode is ^(touch each one^)
echo   viz gain           re-measure force-scale gains ^(press each electrode with the same force^)
echo   viz check          step through S0..S23 one channel at a time
echo   viz stop           close the running viewer
echo   viz restart hand   restart ^(graph / hand / handraw / calib / gain / check^)
echo   viz status         show what is running and whether packets arrive
echo   viz help           this help
echo.
echo Only one viewer can use the COM port at a time.  Keep hands off for ~1 s after start ^(baseline^).
echo Heatmap keys: r or REC button = start/stop recording (MP4 + sensor CSV in Videos\hand_heatmap),
echo               z or ZERO button = zero calibration (hands off 3 s), b = re-baseline, g = gains on/off, +/- = colour max ^(default 100^),
echo               a = divide by electrode area, l = labels, [ / ] or slider = low-pass filter strength
goto :eof
