# Blue Music Suno Compatibility Runtime

This branch is based on `gcui-art/suno-api` commit
`a2e6a823428903af715d3835d1cb44ffa336021d` and is used only as an isolated
compatibility service for Blue Music.

## Security Boundary

- The server binds to `127.0.0.1` by default.
- Every API route requires `Authorization: Bearer <INTERNAL_API_TOKEN>`.
- Incoming `Cookie` headers are rejected.
- The Suno Cookie exists only in `.env.local` and is never returned by an API.
- Automated CAPTCHA solving, browser automation, fingerprint evasion, and
  2Captcha dependencies are removed.
- When Suno requires hCaptcha, the service returns HTTP `409` with
  `SUNO_HUMAN_VERIFICATION_REQUIRED`. An administrator must complete the
  challenge through the normal Suno website and then refresh the local Cookie.

## Build And Run

```powershell
D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd run build:compat
D:\DevTools\Node20\node-v20.20.2-win-x64\node.exe --env-file=.env.local compat-dist\compat-server.js
```

Required local settings:

```dotenv
INTERNAL_API_TOKEN=<random internal token>
COMPAT_HOST=127.0.0.1
COMPAT_PORT=3000
SUNO_COOKIE_BASE64=<local base64 encoded Cookie>
```

Use the following command to update the Cookie through hidden terminal input:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\set-suno-cookie.ps1
```

Do not paste the Cookie into chat, source code, logs, or Git.

## Blue Music Contract

```text
GET  /api/health
POST /api/custom_generate
POST /api/extend_audio
GET  /api/get?ids=...
GET  /api/get_limit
```

This is an unofficial compatibility implementation and can stop working when
Suno changes its private web interface. The official Suno API remains the
preferred production implementation.
