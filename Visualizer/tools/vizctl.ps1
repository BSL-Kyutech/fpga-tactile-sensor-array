# Start / stop the visualizers in their own cmd window (Windows).  Normally called through viz.cmd.
#   powershell -ExecutionPolicy Bypass -File vizctl.ps1 start|stop|restart|status|shot [graph|hand|handraw|calib|gain|check]
# Python: $env:VIZ_PYTHON if set, else the per-user Python 3.13 from winget, else "python" on PATH.
param([ValidateSet('start','stop','restart','status','shot')][string]$Action = 'status',
      [ValidateSet('graph','hand','handraw','nocal','zero','check','calib','gain')][string]$Target = 'graph')
$Repo   = (Resolve-Path "$PSScriptRoot\..\..").Path
$Python = if ($env:VIZ_PYTHON) { $env:VIZ_PYTHON }
          elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe") { "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" }
          else { 'python' }
$Probe  = "$PSScriptRoot\probe.py"
$Script = @{ graph = 'Visualizer\icepizeroo.py'; hand = 'Visualizer\hand_heatmap.py'; handraw = 'Visualizer\hand_heatmap.py --raw'; zero = 'Visualizer\hand_heatmap.py --zero'; nocal = 'Visualizer\hand_heatmap.py --nocal'; calib = 'Visualizer\hand_calibrate.py'; gain = 'Visualizer\hand_gain_calibrate.py'; check = 'Visualizer\tools\channel_check.py' }[$Target]
$Title  = @{ graph = 'Figure 1'; hand = 'Hand Heatmap'; handraw = 'Hand Heatmap'; zero = 'Hand Heatmap'; nocal = 'Hand Heatmap'; calib = 'Hand Calibration'; gain = 'Gain Calibration'; check = 'Channel Check' }[$Target]
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Get-Viz { Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*icepizeroo.py*' -or $_.CommandLine -like '*hand_heatmap.py*' -or $_.CommandLine -like '*channel_check.py*' -or $_.CommandLine -like '*hand_calibrate.py*' -or $_.CommandLine -like '*hand_gain_calibrate.py*' } }

function Show-Status {
    $p = Get-Viz
    if (-not $p) { Write-Output 'STOPPED'; return }
    foreach ($x in $p) {
        $t = (Get-Process -Id $x.ProcessId -ea 0).MainWindowTitle
        Write-Output "RUNNING pid=$($x.ProcessId) title='$t'"
    }
}

function Stop-Viz {
    Get-Viz | % { Stop-Process -Id $_.ProcessId -Force; Write-Output "stopped pid=$($_.ProcessId)" }
    # close the 'Tactile Visualizer' cmd windows left behind by cmd /k
    Get-Process cmd -ea 0 | ? { $_.MainWindowTitle -like 'Tactile Visualizer*' } | Stop-Process -Force
}

function Start-Viz {
    if (Get-Viz) { Write-Output 'already running'; Show-Status; return }
    & $Python $Probe
    if ($LASTEXITCODE -ne 0) { Write-Output "probe failed (exit $LASTEXITCODE) - not starting"; exit 1 }
    Start-Sleep -Milliseconds 300   # let the probe release the port
    Start-Process cmd.exe -WorkingDirectory $Repo -ArgumentList ('/k title Tactile Visualizer && "' + $Python + '" ' + $Script)
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        $p = Get-Viz | select -First 1
        if ($p -and (Get-Process -Id $p.ProcessId -ea 0).MainWindowTitle -eq $Title) { Write-Output "OK: $Title shown (pid=$($p.ProcessId))"; return }
    }
    Write-Output "NG: $Title did not appear within 20 s - check the cmd window"; exit 1
}

function Save-Shot {
    Add-Type -AssemblyName System.Drawing
    Add-Type @'
using System; using System.Runtime.InteropServices;
public class W { [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Rt, B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
    [W]::SetProcessDPIAware() | Out-Null
    $p = Get-Viz | select -First 1
    if (-not $p) { Write-Output 'not running'; exit 1 }
    $h = (Get-Process -Id $p.ProcessId).MainWindowHandle
    [W]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 400
    $r = New-Object W+R; [W]::GetWindowRect($h, [ref]$r) | Out-Null
    $bmp = New-Object Drawing.Bitmap ($r.Rt - $r.L), ($r.B - $r.T)
    [Drawing.Graphics]::FromImage($bmp).CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
    $out = "$env:TEMP\viz_shot_$(Get-Date -f HHmmss).png"; $bmp.Save($out); Write-Output $out
}

switch ($Action) {
    'start'   { Start-Viz }
    'stop'    { Stop-Viz }
    'restart' { Stop-Viz; Start-Sleep 1; Start-Viz }
    'status'  { Show-Status; & $Python $Probe 2>&1 | Select -Last 1 }
    'shot'    { Save-Shot }
}
