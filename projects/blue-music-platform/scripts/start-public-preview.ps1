[CmdletBinding()]
param(
    [string]$CloudflaredPath = 'D:\DevTools\Cloudflared\cloudflared.exe',
    [string]$NpmPath = 'D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd',
    [int]$PreviewPort = 4173,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$logRoot = 'D:\DevTools\Logs\BlueMusic'
$previewStdout = Join-Path $logRoot 'public-preview.stdout.log'
$previewStderr = Join-Path $logRoot 'public-preview.stderr.log'
$tunnelStdout = Join-Path $logRoot 'cloudflared.stdout.log'
$tunnelStderr = Join-Path $logRoot 'cloudflared.stderr.log'
$publicUrlFile = Join-Path $logRoot 'public-url.txt'

if (-not (Test-Path -LiteralPath $CloudflaredPath)) {
    throw "cloudflared not found: $CloudflaredPath"
}
if (-not (Test-Path -LiteralPath $NpmPath)) {
    throw "npm not found: $NpmPath"
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$health = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$BackendPort/api/v1/health/database" `
    -TimeoutSec 10
if ($health.status -ne 'healthy') {
    throw 'Blue Music backend or database is not healthy.'
}

Push-Location $frontendRoot
try {
    & $NpmPath run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$previewProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'node.exe' -and
    $_.CommandLine -match 'vite(\.js)?\s+preview' -and
    $_.CommandLine -match "--port\s+$PreviewPort"
}
$previewProcesses | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

$preview = Start-Process `
    -FilePath $NpmPath `
    -ArgumentList 'run', 'preview', '--', '--host', '127.0.0.1', '--port', "$PreviewPort" `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $previewStdout `
    -RedirectStandardError $previewStderr `
    -PassThru

$previewReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:$PreviewPort/" `
            -UseBasicParsing `
            -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $previewReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $previewReady) {
    Stop-Process -Id $preview.Id -Force -ErrorAction SilentlyContinue
    throw "Frontend preview did not start. See $previewStderr"
}

$tunnelProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'cloudflared.exe' -and
    $_.CommandLine -match 'tunnel' -and
    $_.CommandLine -match "127\.0\.0\.1:$PreviewPort"
}
$tunnelProcesses | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

$tunnel = Start-Process `
    -FilePath $CloudflaredPath `
    -ArgumentList 'tunnel', '--url', "http://127.0.0.1:$PreviewPort", '--no-autoupdate' `
    -WorkingDirectory (Split-Path -Parent $CloudflaredPath) `
    -WindowStyle Hidden `
    -RedirectStandardOutput $tunnelStdout `
    -RedirectStandardError $tunnelStderr `
    -PassThru

$publicUrl = $null
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    $combinedLog = @()
    if (Test-Path -LiteralPath $tunnelStdout) {
        $combinedLog += Get-Content -LiteralPath $tunnelStdout -Raw
    }
    if (Test-Path -LiteralPath $tunnelStderr) {
        $combinedLog += Get-Content -LiteralPath $tunnelStderr -Raw
    }
    $match = [regex]::Match(
        ($combinedLog -join "`n"),
        'https://[a-z0-9-]+\.trycloudflare\.com'
    )
    if ($match.Success) {
        $publicUrl = $match.Value
        break
    }
    if ($tunnel.HasExited) {
        throw "Cloudflare Tunnel exited early. See $tunnelStderr"
    }
}
if (-not $publicUrl) {
    Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
    throw "Cloudflare Tunnel did not return a public URL. See $tunnelStderr"
}

Set-Content -LiteralPath $publicUrlFile -Value $publicUrl -Encoding ascii

[pscustomobject]@{
    PublicUrl = $publicUrl
    PreviewProcessId = $preview.Id
    TunnelProcessId = $tunnel.Id
    UrlFile = $publicUrlFile
}
