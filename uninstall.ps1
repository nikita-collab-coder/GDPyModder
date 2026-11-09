# PyModder: removes the loader (the pymodder folder with your mods stays unless you use -Purge)
param([string]$GDPath, [switch]$Purge)
$ErrorActionPreference = 'Stop'
if (-not $GDPath) {
    $c = @()
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if ($steam) { $c += Join-Path $steam 'steamapps\common\Geometry Dash' }
    $c += 'C:\Program Files (x86)\Steam\steamapps\common\Geometry Dash'
    $GDPath = $c | Where-Object { Test-Path (Join-Path $_ 'GeometryDash.exe') } | Select-Object -First 1
}
if (-not $GDPath) { $GDPath = (Read-Host 'Path to the Geometry Dash folder').Trim('"') }
while (Get-Process GeometryDash -ErrorAction SilentlyContinue) {
    Read-Host 'Geometry Dash is running: close it and press Enter' | Out-Null
}
try {
    foreach ($n in 'XInput1_4.dll', 'opengl32.dll', 'version.dll') {
        $p = Join-Path $GDPath $n
        if (Test-Path $p) {
            $txt = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($p))
            if ($txt.Contains('pymodder_hook') -or $txt.Contains('gdpy_hook')) { Remove-Item $p -Force; Write-Host "Removed $n" }
        }
        if ((Test-Path "$p.bak") -and -not (Test-Path $p)) { Move-Item "$p.bak" $p -Force; Write-Host "Restored the previous $n" }
    }
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PyModder Mods.lnk'
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
    $pm = Join-Path $GDPath 'pymodder'
    if ($Purge) { if (Test-Path $pm) { Remove-Item $pm -Recurse -Force; Write-Host 'Deleted the pymodder folder' } }
    else {
        if (Test-Path (Join-Path $pm 'install.json')) { Remove-Item (Join-Path $pm 'install.json') -Force }
        Write-Host 'The pymodder folder (mods, saves, logs) was kept: delete it by hand if you want.'
    }
    Write-Host 'PyModder is uninstalled.' -ForegroundColor Green
} catch {
    $a = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -GDPath `"$GDPath`""
    if ($Purge) { $a += ' -Purge' }
    Start-Process powershell -Verb RunAs -ArgumentList $a
    exit 0
}
Read-Host 'Press Enter' | Out-Null
