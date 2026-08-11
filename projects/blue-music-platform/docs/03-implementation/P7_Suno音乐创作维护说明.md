# P7 SunoProvider 音乐创作维护说明

更新时间：2026-08-11

## 当前状态

蓝乐业务层只认识统一的 `suno` Provider，实际实现可通过
`SUNO_PROVIDER_IMPLEMENTATION` 选择：

- `official`：默认实现。等待 Suno Platform 账号内正式 API 文档、API Key
  和商用权限；合同未知时明确返回 `SUNO_API_CONTRACT_PENDING`，不猜测路径。
- `compatibility`：对隔离部署的 `gcui-art/suno-api` 做兼容适配。默认关闭，
  只允许本机或 Docker 内网地址，不把 Suno Cookie 传给蓝乐或智能体。

当前本机演示环境已选择 `compatibility`。隔离服务运行在
`http://127.0.0.1:3000`；服务、内部令牌、管理员登录会话和真实额度查询均已
联通。真实音乐生成会消耗账户额度，尚未在未获确认时擅自执行。会话缺失时状态
必须回落到 `waiting_session`，不得冒充 `ready`。

其他 Agent、自动流程和前端始终调用：

```text
POST /api/v1/music/tasks
-> services/music.py
-> Redis music queue
-> app.workers.music
-> MusicGenerationProvider
-> official 或 compatibility
```

切换实现不需要修改采集、分析、作词、工作流或前端代码。环境配置变化后，
新任务使用新实现；已经入队的任务继续使用创建时记录的
`provider_implementation`，避免外部任务编号串线。

## 创作参数与任务模型

音乐创作请求可携带多个目标风格标签和多个避免风格标签；服务端拒绝两组标签
重叠的请求。管理员维护唯一的 `music_provider_settings` 记录，当前活动模型默认
为 `v4.5`。只有超级管理员可以通过 `PUT /api/v1/music/settings` 修改它，变更只
影响之后创建的任务；每个任务会保存实际使用的模型与风格标签。

`POST /api/v1/music/tasks/{task_id}/regenerate` 会以来源任务的创作参数创建一个新
任务，返回 `202`；原任务和已产出的试听/下载结果不被覆盖。授权改编通过
`POST /api/v1/music/adaptations` 提交，必须明确 `rights_confirmed=true`，并保存
来源标题、作者/来源链接和权利说明以供内部追溯。该入口不等同于对未授权作品的
复制或模仿承诺。

## 开源兼容项目审计

审计仓库：`https://github.com/gcui-art/suno-api`

审计提交：

```text
a2e6a823428903af715d3835d1cb44ffa336021d
```

可复现补丁和安装脚本保存在：

```text
integrations/suno-compat/
```

当前机器的隔离运行副本位于 `D:\DevTools\SunoCompat`，本地安全分支提交为
`99cec07`。`.env.local`、内部令牌、Suno Cookie、日志和编译产物均不进入 Git。

已适配的外部合同：

| 能力 | 兼容服务路径 |
|---|---|
| 自定义生成 | `POST /api/custom_generate` |
| 续写 | `POST /api/extend_audio` |
| 查询结果 | `GET /api/get?ids=...` |
| 查询额度 | `GET /api/get_limit` |

兼容层会归一化标题、歌词、风格、排除标签、模型、音频编号、状态、时长、
封面、额度和错误。它不会把该项目直接暴露给调度智能体，也不会接受前端
传入 Cookie。

该开源项目是 LGPL-3.0-or-later 的非官方研究项目，内部包含 2Captcha、
Playwright、浏览器指纹规避和 Cookie 网页接口。蓝乐不复制、不启用这些
验证码代答或规避机制。检测到 hCaptcha 时：

```text
外部返回 CAPTCHA
-> SUNO_HUMAN_VERIFICATION_REQUIRED
-> task.status = failed
-> provider_status = waiting_human_verification
-> 管理员在正常 Suno 网页完成人工验证并更新隔离服务会话
-> POST /music/tasks/{id}/retry
```

正常情况下生成、轮询、下载和工作流仍为全自动，只有 Suno 主动要求真人
验证时才需要人工。

## 可靠任务执行

音乐任务不再由 FastAPI `BackgroundTasks` 直接调用供应商。API 只写数据库
并入 Redis 队列，独立 worker 负责外部调用：

```powershell
cd D:\SunJX\projects\blue-music-platform\backend
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m app.workers.music
```

可靠性规则：

- Redis 使用待处理、处理中和延迟重试三个队列。
- worker 启动时恢复处理中断和数据库中的 pending 任务。
- 全局并发槽由 Redis 锁控制，默认最多 `1` 个 Suno 任务。
- 新生成或续写任务的全局启动间隔默认 `30` 秒，多个 worker 共享同一限频状态；
  结果轮询也默认每 `30` 秒一次。
- 429、5xx、网络超时和生成超时按指数退避重试。
- 401/403、额度不足、参数错误和 hCaptcha 不盲目自动重试。
- 外部任务编号一旦获得就持久化；超时重试优先继续查询同一任务。
- 运行租约覆盖提交、轮询和最多四个结果文件的归档时间，避免归档期间被误判中断。
- 任务记录 `attempt_count`、`max_attempts`、`next_attempt_at` 和错误详情。

主要错误码：

| 错误码 | 含义 | 自动重试 |
|---|---|---|
| `SUNO_API_NOT_CONFIGURED` | 官方地址或 Key 缺失 | 否 |
| `SUNO_API_CONTRACT_PENDING` | 官方文档尚未完成映射 | 否 |
| `SUNO_COMPAT_DISABLED` | 兼容实现未显式启用 | 否 |
| `SUNO_COOKIE_NOT_CONFIGURED` | 隔离服务尚未配置 Suno 登录会话 | 否 |
| `SUNO_COMPAT_AUTH_FAILED` | 蓝乐与隔离服务的内部令牌不一致 | 否 |
| `SUNO_HUMAN_VERIFICATION_REQUIRED` | 需要人工完成 hCaptcha | 否 |
| `SUNO_SESSION_EXPIRED` | 兼容会话失效 | 否 |
| `SUNO_QUOTA_EXHAUSTED` | 账户额度不足 | 否 |
| `SUNO_RATE_LIMITED` | 供应商限频 | 是 |
| `SUNO_COMPAT_UPSTREAM_ERROR` | 兼容服务或上游 5xx | 是 |
| `SUNO_GENERATION_TIMEOUT` | 等待结果超时 | 是，继续查询 |
| `MUSIC_QUEUE_UNAVAILABLE` | Redis 队列不可用 | 手工重试 |

## 额度与对象存储

额度分为两层：

1. **Suno 供应商额度**：超级管理员可在音乐创作页查看真实剩余积分、本期用量
   和快照时间。普通员工不展示团队账户总余额。
2. **员工音乐任务额度**：新生成和续写各扣 `1` 次；worker 重试不重复扣除；
   超级管理员不限额，普通员工默认 `0` 次。

超级管理员可调用：

```text
GET  /api/v1/music/provider-status
POST /api/v1/music/provider-status/refresh
PUT  /api/v1/users/{user_id}/music-quota
```

额度快照保存到 `music_provider_quota_snapshots`。兼容实现读取
`credits_left/monthly_usage/monthly_limit/period`；官方实现等正式文档后映射。

员工额度保存在 `users.music_quota_remaining/music_quota_used`。创建音乐任务时
通过数据库行锁完成扣减，额度不足返回 `MUSIC_TASK_QUOTA_EXHAUSTED`，不会创建
任务。任务提交后即占用额度；供应商失败或用户删除任务/结果时不自动返还，
管理员可在账号管理页核实后调整当前剩余次数。

对象存储由 `MUSIC_STORAGE_BACKEND` 选择：

- `local`：默认保存到 `backend/storage/music`。
- `s3`：支持 AWS S3、MinIO 和其他 S3-compatible 服务，试听和下载使用短期
  预签名 URL。

下载器只接受 HTTPS 公网音频地址，限制重定向次数、响应类型和最大文件大小，
并拒绝回环、内网和链路本地地址，降低 SSRF 风险。

## 关键配置

```dotenv
SUNO_PROVIDER_IMPLEMENTATION=official

SUNO_API_BASE_URL=
SUNO_API_KEY=
SUNO_MODEL=

SUNO_COMPAT_ENABLED=false
SUNO_COMPAT_BASE_URL=http://suno-compat:3000
SUNO_COMPAT_SHARED_TOKEN=
SUNO_COMPAT_MODEL=
SUNO_COMPAT_ALLOW_REMOTE=false

MUSIC_QUEUE_MODE=redis
MUSIC_MAX_CONCURRENCY=1
MUSIC_MIN_REQUEST_INTERVAL_SECONDS=30
SUNO_POLL_INTERVAL_SECONDS=30
MUSIC_MAX_RETRIES=3
MUSIC_RETRY_BASE_SECONDS=30
MUSIC_RETRY_MAX_SECONDS=600

MUSIC_STORAGE_BACKEND=local
MUSIC_STORAGE_DIR=
```

兼容服务若需要跨主机访问，必须由内网网关校验
`SUNO_COMPAT_SHARED_TOKEN`，同时使用 HTTPS。Suno Cookie 只放在隔离兼容服务
的密钥环境中，禁止进入蓝乐数据库、前端、日志、文档和 Git。

## 官方联调入口

Suno Platform 当前公开页只说明提供 REST API，详细合同登录后才可见。拿到
权限后只需完成 `SunoOfficialMusicProvider`：

1. 按正式文档映射认证、生成、续写、查询和额度。
2. 使用官方幂等键、回调或轮询建议。
3. 映射官方状态、请求编号、计费单位和 Retry-After。
4. 用中文歌词验收生成、失败、超时、续写、额度和下载。

不得用推测的路径或字段冒充官方联调成功。

## 测试

```powershell
cd D:\SunJX\projects\blue-music-platform\backend
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m pytest -q

cd ..\frontend
npm.cmd run test
npm.cmd run lint
npm.cmd run build
```

当前基线：后端 `77` 个测试，前端 `15` 个测试。兼容适配器测试覆盖生成归一化、
额度、运行状态、未配置会话、429、响应级与任务级 hCaptcha、混合结果失败和
远程 HTTP 拒绝；平台测试覆盖持久重试、人工验证状态、重新入队、试听、下载、
删除、员工额度扣减/耗尽、管理员分配和工作流传参。
