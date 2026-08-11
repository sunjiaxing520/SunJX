# Suno Compatibility Integration

This directory makes the reviewed `gcui-art/suno-api` compatibility runtime
reproducible without committing a Suno Cookie or internal token.

## Pinned Source

- Upstream: `https://github.com/gcui-art/suno-api`
- Commit: `a2e6a823428903af715d3835d1cb44ffa336021d`
- Blue Music patch:
  `0001-Add-isolated-Blue-Music-compatibility-runtime.patch`

The patch removes automated CAPTCHA solving, browser automation, fingerprint
evasion, and the related dependencies. The resulting service binds to
`127.0.0.1`, requires an internal Bearer token, rejects inbound Cookies, and
returns a human-verification error when Suno requests hCaptcha.

## Recreate The Runtime

Run from PowerShell:

```powershell
cd D:\SunJX\projects\blue-music-platform\integrations\suno-compat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\configure-local.ps1
```

`install.ps1` clones the pinned upstream revision into
`D:\DevTools\SunoCompat`, applies the reviewed patch, installs dependencies,
and builds the lightweight compatibility server. It refuses to overwrite an
existing directory.

`configure-local.ps1` generates one random internal token and writes it to the
two ignored local environment files that need it. It does not configure the
Suno Cookie and never prints the token.

To enter the Suno Cookie locally with hidden terminal input:

```powershell
cd D:\DevTools\SunoCompat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\set-suno-cookie.ps1
```

Then restart the compatibility service. Never paste the Cookie into chat,
source code, logs, documentation, or Git.

## Runtime Status

The compatibility service exposes an authenticated `GET /api/health` endpoint:

- `ready`: a local Suno session is configured.
- `waiting_cookie`: the service is running but needs the administrator to
  configure a session.

Blue Music maps these states to `ready` and `waiting_session`. The official
Suno Provider remains the preferred production implementation because this
compatibility runtime relies on an unofficial private web interface.
