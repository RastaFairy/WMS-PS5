<#
  ps5-native-app-boilerplate - Windows build entry point.
  Copyright (C) 2026 BlackBearReloaded
  SPDX-License-Identifier: GPL-3.0-or-later

  Runs the canonical Linux/WSL build so both host entry points share one
  metadata parser and one packaging pipeline.

  By default the project is mirrored into the WSL Linux filesystem, built there
  (symbolic links and compilers work normally), and the resulting dist/ folder is
  copied back next to the sources. Set PS5_BUILD_IN_PLACE=1 to build directly on
  the Windows drive instead; that needs Windows Developer Mode or an elevated shell
  for the symbolic links the build creates.
#>

#requires -Version 5.1
$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    throw "ps5-native-app-boilerplate: $Message"
}

function Convert-ToWslPath([string]$Path) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if ($absolute -notmatch '^([A-Za-z]):\\(.*)$') {
        Fail "The repository must be on a Windows drive visible to WSL."
    }
    return "/mnt/$($Matches[1].ToLowerInvariant())/$($Matches[2].Replace('\', '/'))"
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Fail "WSL was not found. Install WSL and a Linux distribution first."
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$wslRoot = Convert-ToWslPath $root
$inPlace = $env:PS5_BUILD_IN_PLACE -eq "1"
$arguments = @("--exec", "env")
foreach ($name in @(
        "APP_DEFINITIONS",
        "APP_INCLUDE_PATHS",
        "APP_STATIC_ARCHIVES",
        "APP_IMPORT_STUBS",
        "APP_RUNTIME_MODULES",
        "PS5_OPENGL_PREFIX",
        "PS5_WSL_WORKDIR",
        "BUILD_JOBS",
        "USE_CCACHE",
        "PACBREW_PACKAGES",
        "PACBREW_INCLUDE_PATHS",
        "PACBREW_STATIC_ARCHIVES")) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($null -ne $value) {
        $arguments += "${name}=$value"
    }
}
if ($inPlace) {
    $arguments += @("make", "-C", $wslRoot, "app")
} else {
    $arguments += @("bash", "$wslRoot/tools/wsl-build.sh", $wslRoot, "app")
}
& wsl.exe @arguments
if ($LASTEXITCODE -ne 0) {
    Fail "The WSL build failed."
}
if (-not $inPlace) {
    Write-Host "ps5-native-app-boilerplate: result returned to $(Join-Path $root 'dist')"
}
