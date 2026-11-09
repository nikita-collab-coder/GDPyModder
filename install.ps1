# PyModder: installs the Python mod loader into Geometry Dash (fallback for "PyModder Setup.exe")
param([string]$GDPath, [ValidateSet('auto', 'XInput1_4.dll', 'opengl32.dll', 'version.dll')][string]$Loader = 'auto',
      [switch]$NoExamples, [switch]$NoShortcut)
$ErrorActionPreference = 'Stop'
$Version = '0.7.0-beta'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here 'files'
$srcPM = Join-Path $src 'pymodder'
$names = @('XInput1_4.dll', 'opengl32.dll', 'version.dll')

function Find-GD {
    $c = @()
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if ($steam) {
        $c += Join-Path $steam 'steamapps\common\Geometry Dash'
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path $vdf) {
            Select-String -Path $vdf -Pattern '"path"\s+"(.+?)"' | ForEach-Object {
                $c += Join-Path ($_.Matches[0].Groups[1].Value -replace '\\\\', '\') 'steamapps\common\Geometry Dash'
            }
        }
    }
    $c += 'C:\Program Files (x86)\Steam\steamapps\common\Geometry Dash'
    foreach ($p in $c) { if (Test-Path (Join-Path $p 'GeometryDash.exe')) { return (Resolve-Path $p).Path } }
    return $null
}

function Done($code) { Write-Host ''; Read-Host 'Press Enter to close' | Out-Null; exit $code }

# 0 = no file, 1 = PyModder (or old gdpy) loader, 2 = another mod's dll
function Loader-State($path) {
    if (-not (Test-Path $path)) { return 0 }
    $txt = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($path))
    if ($txt.Contains('pymodder_hook') -or $txt.Contains('gdpy_hook')) { return 1 }
    return 2
}

function Restore-Bak($dll) {
    if ((Test-Path "$dll.bak") -and -not (Test-Path $dll)) {
        Move-Item "$dll.bak" $dll -Force
        Write-Host "Restored the previous $(Split-Path -Leaf $dll) (from .bak)"
    }
}

try { $Host.UI.RawUI.WindowTitle = 'PyModder Setup' } catch {}
Write-Host "=== PyModder ${Version}: Python mods for Geometry Dash ===" -ForegroundColor Magenta
if (-not (Test-Path (Join-Path $srcPM 'core'))) { Write-Host "The files folder was not found next to the installer: $src" -ForegroundColor Red; Done 1 }

$gd = if ($GDPath) { $GDPath } else { Find-GD }
if (-not $gd) { $gd = (Read-Host 'Geometry Dash was not found. Paste the path to the Geometry Dash folder').Trim('"') }
if (-not (Test-Path (Join-Path $gd 'GeometryDash.exe'))) { Write-Host "GeometryDash.exe is not in this folder: $gd" -ForegroundColor Red; Done 1 }
Write-Host "Game folder: $gd"

while (Get-Process GeometryDash -ErrorAction SilentlyContinue) {
    Read-Host 'Geometry Dash is running: close it and press Enter' | Out-Null
}

$probe = Join-Path $gd 'pymodder_test.tmp'
try { [IO.File]::WriteAllText($probe, 'x'); Remove-Item $probe }
catch {
    Write-Host 'Administrator rights are needed, asking...' -ForegroundColor Yellow
    $a = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -GDPath `"$gd`" -Loader $Loader"
    if ($NoExamples) { $a += ' -NoExamples' }
    if ($NoShortcut) { $a += ' -NoShortcut' }
    Start-Process powershell -Verb RunAs -ArgumentList $a
    exit 0
}

try {
    # --- the loader dll: XInput1_4.dll, or opengl32.dll if XInput1_4.dll belongs to another mod (Geode, Mega Hack...)
    $paths = $names | ForEach-Object { Join-Path $gd $_ }
    $st = $paths | ForEach-Object { Loader-State $_ }
    if ($Loader -eq 'auto') {
        if ($st[0] -eq 1 -and (Loader-State "$($paths[0]).bak") -eq 2) {
            Remove-Item $paths[0] -Force
            Move-Item "$($paths[0]).bak" $paths[0] -Force
            Write-Host 'XInput1_4.dll belongs to another mod loader: restored it from .bak'
            $st[0] = 2
        }
        if ($st[0] -ne 2) { $pick = 0 }
        elseif ($st[1] -ne 2) { $pick = 1; Write-Host 'XInput1_4.dll is used by another mod, so PyModder uses opengl32.dll' }
        else { throw 'XInput1_4.dll and opengl32.dll are both used by other mods. Run again with -Loader version.dll' }
    } else {
        $pick = 0; for ($i = 0; $i -lt 3; $i++) { if ($names[$i] -eq $Loader) { $pick = $i } }
        if ($st[$pick] -eq 2) {
            Move-Item $paths[$pick] "$($paths[$pick]).bak" -Force
            Write-Host "Saved the other $($names[$pick]) as $($names[$pick]).bak"
        }
    }
    Copy-Item (Join-Path $src "loaders\$($names[$pick])") $paths[$pick] -Force
    Write-Host "Loader: $($names[$pick])"
    for ($i = 0; $i -lt 3; $i++) {
        if ($i -ne $pick -and (Loader-State $paths[$i]) -eq 1) {
            Remove-Item $paths[$i] -Force
            Write-Host "Removed the old PyModder $($names[$i])"
            Restore-Bak $paths[$i]
        }
    }

    $dst = Join-Path $gd 'pymodder'
    $mods = Join-Path $dst 'mods'
    New-Item -ItemType Directory -Force -Path $dst, $mods, (Join-Path $dst 'logs') | Out-Null

    # --- moving from the old gdpy
    $old = Join-Path $gd 'gdpy'
    if (Test-Path $old) {
        Write-Host 'Found the old gdpy: moving its mods and settings...' -ForegroundColor Yellow
        $oldCfg = Join-Path $old 'config.json'
        if ((Test-Path $oldCfg) -and -not (Test-Path (Join-Path $dst 'config.json'))) { Copy-Item $oldCfg $dst }
        $oldMods = Join-Path $old 'mods'
        if (Test-Path $oldMods) {
            # unchanged gdpy 0.1 examples are not moved: newer versions replace them
            $stock = @('b32ccce3daa011c5e9fd2a1fb6b356f25fc9580f1bf1055601e492719c909977',
                       '08e7f5fbe3f4bd12f346da81672d4b6398e1acdcc22b80e14e30e61234f1c44f',
                       'bfc37cc6bfdfca6d59ac0abff68d578aa09f7f0c6a7a1d348802edeabfdada58',
                       '7588e39d163ba25e773c0ca2a8d2d56e53b957ca5e625392fe5ef781f44a9afb')
            Get-ChildItem $oldMods | Where-Object { $_.Name -ne 'data' -and $_.Name -ne '__pycache__' } | ForEach-Object {
                $t = Join-Path $mods $_.Name
                $isStock = (-not $_.PSIsContainer) -and ($stock -contains (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())
                if (-not $isStock -and -not (Test-Path $t)) { Move-Item $_.FullName $t }
            }
            $oldData = Join-Path $oldMods 'data'
            if (Test-Path $oldData) {
                $newData = Join-Path $mods 'data'
                New-Item -ItemType Directory -Force -Path $newData | Out-Null
                Get-ChildItem $oldData | ForEach-Object {
                    $t = Join-Path $newData $_.Name
                    if (-not (Test-Path $t)) { Move-Item $_.FullName $t }
                }
            }
        }
        Remove-Item $old -Recurse -Force
    }

    # --- PyModder files
    foreach ($d in 'core', 'bindings', 'python', 'docs', 'res', 'sdk') {
        $t = Join-Path $dst $d
        if (Test-Path $t) { Remove-Item $t -Recurse -Force }
        Copy-Item (Join-Path $srcPM $d) $t -Recurse -Force
    }

    # --- example mods: new ones are added, unchanged ones from older versions are updated
    $stock = @(Get-Content (Join-Path $here 'stock_mods.txt') -ErrorAction SilentlyContinue)
    $srcMods = Join-Path $srcPM 'mods'
    $added = 0; $updated = 0
    Get-ChildItem $srcMods -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($srcMods.Length + 1)
        $t = Join-Path $mods $rel
        if (Test-Path $t) {
            $h = (Get-FileHash $t -Algorithm SHA256).Hash.ToLower()
            if ($stock -contains $h -and $h -ne (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()) {
                Copy-Item $_.FullName $t -Force; $updated++
            }
        } elseif (-not $NoExamples -or $_.Name.StartsWith('_')) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $t) | Out-Null
            Copy-Item $_.FullName $t; $added++
        }
    }
    if ($added -or $updated) { Write-Host "Example mods: $added added, $updated updated" }

    $cfgPath = Join-Path $dst 'config.json'
    if (-not (Test-Path $cfgPath)) { Copy-Item (Join-Path $srcPM 'config.json') $cfgPath }
    if (Test-Path (Join-Path $dst 'disabled')) { Remove-Item (Join-Path $dst 'disabled') -Force }
    $info = [ordered]@{ version = $Version; loader = $names[$pick]; installed = (Get-Date -Format 'yyyy-MM-dd HH:mm') }
    [IO.File]::WriteAllText((Join-Path $dst 'install.json'), ($info | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))

    # --- desktop shortcut
    if (-not $NoShortcut) {
        try {
            $desk = [Environment]::GetFolderPath('Desktop')
            $sh = New-Object -ComObject WScript.Shell
            $lnk = $sh.CreateShortcut((Join-Path $desk 'PyModder Mods.lnk'))
            $lnk.TargetPath = $mods
            $lnk.IconLocation = (Join-Path $dst 'res\pymodder.ico') + ',0'
            $lnk.Description = 'PyModder mods folder'
            $lnk.Save()
            Write-Host 'Desktop shortcut "PyModder Mods" created'
        } catch { Write-Host 'Could not create the shortcut (not a problem)' -ForegroundColor DarkYellow }
    }
}
catch {
    Write-Host ''
    Write-Host "Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    Done 1
}

Write-Host ''
Write-Host 'Done! Start Geometry Dash as usual (through Steam).' -ForegroundColor Green
Write-Host "Mods: $mods"
Write-Host 'In game: the PyModder button in the main menu or F6 opens the mods menu, F5 reloads mods.'
Write-Host 'How to write mods: pymodder\docs\API.md. Logs: pymodder\logs'
try { Start-Process explorer.exe $mods } catch {}
Done 0
