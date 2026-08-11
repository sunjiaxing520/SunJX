[CmdletBinding()]
param(
    [string]$InstallRoot = 'D:\DevTools\SunoCompat'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$projectEnv = Join-Path $projectRoot '.env'
$compatEnv = Join-Path $InstallRoot '.env.local'

if (-not (Test-Path -LiteralPath $InstallRoot)) {
    throw "Compatibility runtime is missing: $InstallRoot"
}
if (-not (Test-Path -LiteralPath $projectEnv)) {
    throw "Blue Music local environment is missing: $projectEnv"
}

$compatLines = if (Test-Path -LiteralPath $compatEnv) {
    @(Get-Content -LiteralPath $compatEnv)
} else {
    @()
}
$tokenLine = $compatLines |
    Where-Object { $_.StartsWith('INTERNAL_API_TOKEN=') } |
    Select-Object -First 1
$token = if ($tokenLine) { ($tokenLine -split '=', 2)[1] } else { $null }

if ([string]::IsNullOrWhiteSpace($token)) {
    $bytes = [byte[]]::new(32)
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    $token = [Convert]::ToBase64String($bytes)
    $token = $token.TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $bytes = $null
}

$preservedRuntimeSettings = @(
    $compatLines | Where-Object {
        $_.StartsWith('SUNO_COOKIE_BASE64=') -or
        $_.StartsWith('HTTP_PROXY=') -or
        $_.StartsWith('HTTPS_PROXY=') -or
        $_.StartsWith('NO_PROXY=')
    }
)
$newCompatLines = @(
    "INTERNAL_API_TOKEN=$token"
    'COMPAT_HOST=127.0.0.1'
    'COMPAT_PORT=3000'
    'NEXT_TELEMETRY_DISABLED=1'
)
if ($preservedRuntimeSettings) {
    $newCompatLines += $preservedRuntimeSettings
}
[IO.File]::WriteAllLines(
    $compatEnv,
    $newCompatLines,
    [Text.UTF8Encoding]::new($false)
)

$managedKeys = @(
    'SUNO_PROVIDER_IMPLEMENTATION',
    'SUNO_COMPAT_ENABLED',
    'SUNO_COMPAT_BASE_URL',
    'SUNO_COMPAT_SHARED_TOKEN',
    'SUNO_COMPAT_ALLOW_REMOTE'
)
$projectLines = @(
    Get-Content -LiteralPath $projectEnv |
        Where-Object {
            $line = $_
            -not ($managedKeys | Where-Object { $line.StartsWith("$_=") })
        }
)
$projectLines += 'SUNO_PROVIDER_IMPLEMENTATION=compatibility'
$projectLines += 'SUNO_COMPAT_ENABLED=true'
$projectLines += 'SUNO_COMPAT_BASE_URL=http://127.0.0.1:3000'
$projectLines += "SUNO_COMPAT_SHARED_TOKEN=$token"
$projectLines += 'SUNO_COMPAT_ALLOW_REMOTE=false'

$temporaryPath = "$projectEnv.tmp"
[IO.File]::WriteAllLines(
    $temporaryPath,
    $projectLines,
    [Text.UTF8Encoding]::new($false)
)
Move-Item -LiteralPath $temporaryPath -Destination $projectEnv -Force

$token = $null
Write-Host 'Local compatibility settings updated without exposing the internal token.'
