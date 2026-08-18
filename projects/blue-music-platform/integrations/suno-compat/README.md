# Suno Compatibility Integration

This directory vendors the reviewed `gcui-art/suno-api` compatibility runtime
in full, without committing a Suno Cookie or internal token.

## Vendored Source

- Upstream: `https://github.com/gcui-art/suno-api`
- Commit: `a2e6a823428903af715d3835d1cb44ffa336021d`
- Full modified source: `runtime/` (authoritative copy)
- Historical patch (reference only):
  `0001-Add-isolated-Blue-Music-compatibility-runtime.patch`

`runtime/` is the complete source tree exactly as deployed on this machine,
including the follow-up hCaptcha handling change documented in
`runtime/CAPTCHA_CHANGE_AND_ROLLBACK.md`. It excludes `.git`, `node_modules`,
build output (`compat-dist/`, `.next/`), `logs/`, and the secret-bearing
`.env.local`.

The modifications keep the service bound to `127.0.0.1`, require an internal
Bearer token, and reject inbound Cookies. hCaptcha handling (updated
2026-08-18, owner-authorized): with `TWOCAPTCHA_KEY` configured, the upstream
automatic solver (rebrowser-playwright + 2Captcha) solves challenges; without
a key the service falls back to the manual flow and returns
`SUNO_HUMAN_VERIFICATION_REQUIRED` when Suno requests hCaptcha.

## Recreate The Runtime

Copy `runtime/` to the deployment directory (this machine uses
`D:\DevTools\SunoCompat`), then install and build:

```powershell
cd D:\DevTools\SunoCompat
npm.cmd ci
npm.cmd run build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\SunJX\projects\blue-music-platform\integrations\suno-compat\configure-local.ps1
```

`configure-local.ps1` generates one random internal token and writes it to the
two ignored local environment files that need it. It does not configure the
Suno Cookie and never prints the token.

The legacy `install.ps1` (clone pinned upstream + apply patch) is kept for
reference; `runtime/` is the authoritative source because it also contains the
post-patch hCaptcha handling change.

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
