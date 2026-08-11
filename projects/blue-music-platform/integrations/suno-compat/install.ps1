[CmdletBinding()]
param(
    [string]$InstallRoot = 'D:\DevTools\SunoCompat',
    [string]$NpmPath = 'D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd',
    [string]$Registry = 'https://registry.npmjs.org'
)

$ErrorActionPreference = 'Stop'
$upstreamCommit = 'a2e6a823428903af715d3835d1cb44ffa336021d'
$patchPath = Join-Path $PSScriptRoot '0001-Add-isolated-Blue-Music-compatibility-runtime.patch'

if (Test-Path -LiteralPath $InstallRoot) {
    throw "InstallRoot already exists: $InstallRoot"
}
if (-not (Test-Path -LiteralPath $patchPath)) {
    throw "Compatibility patch is missing: $patchPath"
}
if (-not (Test-Path -LiteralPath $NpmPath)) {
    throw "npm executable is missing: $NpmPath"
}

$installParent = Split-Path -Parent $InstallRoot
if (-not (Test-Path -LiteralPath $installParent)) {
    New-Item -ItemType Directory -Path $installParent | Out-Null
}

& git clone https://github.com/gcui-art/suno-api.git $InstallRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to clone gcui-art/suno-api.'
}

& git -C $InstallRoot checkout --detach $upstreamCommit
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to check out the pinned upstream commit.'
}

& git -C $InstallRoot switch -c blue-music-safe
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create the blue-music-safe branch.'
}

& git -C $InstallRoot apply $patchPath
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to apply the reviewed Blue Music compatibility patch.'
}

Push-Location $InstallRoot
try {
    & $NpmPath ci --ignore-scripts --no-audit --no-fund --registry=$Registry
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install compatibility runtime dependencies.'
    }
    & $NpmPath run build
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to build the compatibility runtime.'
    }
}
finally {
    Pop-Location
}

Write-Host "Compatibility runtime installed at $InstallRoot"
