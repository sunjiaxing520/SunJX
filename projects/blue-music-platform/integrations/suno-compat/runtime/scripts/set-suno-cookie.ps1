[CmdletBinding()]
param()

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root '.env.local'

if (-not (Test-Path -LiteralPath $envPath)) {
    throw '.env.local does not exist. Initialize the compatibility service first.'
}

$secureCookie = Read-Host 'Paste the Suno Cookie (input is hidden)' -AsSecureString
$cookiePointer = [IntPtr]::Zero

try {
    $cookiePointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureCookie)
    $cookie = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($cookiePointer)
    if ([string]::IsNullOrWhiteSpace($cookie)) {
        throw 'The Suno Cookie cannot be empty.'
    }

    $encodedCookie = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($cookie.Trim())
    )
    $lines = @(
        Get-Content -LiteralPath $envPath |
            Where-Object {
                -not $_.StartsWith('SUNO_COOKIE=') -and
                -not $_.StartsWith('SUNO_COOKIE_BASE64=')
            }
    )
    $lines += "SUNO_COOKIE_BASE64=$encodedCookie"

    $temporaryPath = "$envPath.tmp"
    [IO.File]::WriteAllLines(
        $temporaryPath,
        $lines,
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $envPath -Force
    Write-Host 'Suno Cookie saved locally. Restart the compatibility service to apply it.'
}
finally {
    if ($cookiePointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($cookiePointer)
    }
    $cookie = $null
    $secureCookie = $null
}
