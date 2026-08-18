# 蓝乐 Suno API Kimi 交接文件

最后核对：2026-08-18

## 1. 给 Kimi 的任务说明

请接手蓝乐项目的 Suno API 联调与 Provider 适配。先阅读本文和本文列出的代码，
不要从聊天历史猜测项目结构。

本次工作的目标是：继续维护蓝乐统一的 `MusicGenerationProvider`，完成或修正
Suno 音乐生成能力，同时保持 `official`（Suno 官方 API）与
`compatibility`（`gcui-art/suno-api` 隔离兼容服务）可以通过配置切换。采集、
分析、作词、审核和自动工作流不能直接调用任何 Suno 底层接口。

优先级如下：

1. 获得 Suno Platform 正式 API 文档与访问权限后，优先完成 `official` 实现。
2. 官方合同未齐全时，可以维护现有 `compatibility` 实现，但不能猜测官方路径或
   用兼容接口冒充官方接口。
3. 保留蓝乐现有异步队列、并发与频率限制、任务持久化、失败重试、员工额度、
   供应商额度、音频归档、试听和下载能力。
4. 外部调用失败时必须返回真实失败和稳定错误码，不得伪造成功或音乐结果。

## 2. 仓库与版本位置

### 2.1 蓝乐主仓库

| 项目 | 值 |
|---|---|
| Git SSH 地址 | `git@github.com:sunjiaxing520/SunJX.git` |
| GitHub 页面 | `https://github.com/sunjiaxing520/SunJX` |
| 本机仓库根目录 | `D:\SunJX` |
| 蓝乐项目目录 | `D:\SunJX\projects\blue-music-platform` |
| 当前分支 | `main` |
| 本文编写前提交 | `dc4e2470b95d1f3fa99a4e5f3ac727d59b8667fe` |

开始前必须在 `D:\SunJX` 执行：

```powershell
git status
git pull --ff-only
```

主仓库当前存在与本任务无关的用户改动，禁止恢复、删除或提交：

```text
已删除：D:\SunJX\outputs\无人系统标准中试验验证总体技术路线图_可编辑.pptx
未跟踪：D:\SunJX\outputs\图片转Excel_20260806\
```

提交时只暂存 Suno 任务涉及的明确文件，不要直接使用会包含无关文件的提交方式。

### 2.2 上游非官方兼容项目

| 项目 | 值 |
|---|---|
| 上游项目 | `gcui-art/suno-api` |
| Git 地址 | `https://github.com/gcui-art/suno-api.git` |
| 项目页面 | `https://github.com/gcui-art/suno-api` |
| 许可证 | `LGPL-3.0-or-later` |
| 蓝乐固定的上游提交 | `a2e6a823428903af715d3835d1cb44ffa336021d` |
| 本机隔离克隆 | `D:\DevTools\SunoCompat` |
| 本机适配分支 | `blue-music-safe` |
| 本机适配基线提交 | `99cec077f340d171e3278cb386a246b2c4d0ed57` |

`D:\DevTools\SunoCompat` 是独立 Git 仓库，不属于 `D:\SunJX` 主仓库。本文核对
时，该仓库还有以下未提交状态：

```text
M  src/compat-server.ts
?? CAPTCHA_CHANGE_AND_ROLLBACK.md
```

其中 `src/compat-server.ts` 已增加若干上游能力的轻量路由。接手时先执行
`git diff -- src/compat-server.ts` 阅读并保留这些改动，不得用上游文件直接覆盖。
`CAPTCHA_CHANGE_AND_ROLLBACK.md` 不是蓝乐正式需求或架构文档，不能跳过代码审查
直接照单执行。

### 2.3 Suno 官方入口

- 官方开发平台：`https://platform.suno.com/`
- 当前代码不猜测官方接口合同。需要以用户账号内可见的正式文档为唯一依据。
- API Key、回调密钥、Cookie 和内部共享令牌不得写入本文、聊天、日志或 Git。

## 3. 当前系统调用链

```text
React 前端
  -> POST /api/v1/music/tasks
FastAPI routes/music.py
  -> services/music.py 创建数据库任务并扣员工任务次数
  -> services/music_queue.py 写入 Redis
  -> app.workers.music 独立 worker 取任务
  -> adapters/music_generation.py 的统一 MusicGenerationProvider
       -> SunoOfficialMusicProvider
       或 SunoCompatibilityMusicProvider
  -> 保存外部任务编号
  -> 轮询结果
  -> music_storage.py 下载到本地或 S3-compatible 对象存储
  -> PostgreSQL 保存 MusicTask / MusicResult / 额度快照 / 接口用量
  -> 前端试听、下载或续写
```

自动工作流也只调用蓝乐 `services/music.py`。不要让工作流、审核智能体、作词
智能体或浏览器直接请求 `D:\DevTools\SunoCompat`。

## 4. 蓝乐主仓库文件地图

以下路径均以 `D:\SunJX\projects\blue-music-platform` 为根目录。

### 4.1 首要修改位置

| 文件 | 当前作用 | Kimi 应如何处理 |
|---|---|---|
| `backend/app/adapters/music_generation.py` | 统一输入输出、Provider 协议、官方/兼容实现、状态轮询和错误映射 | **主要修改点**。官方 API 联调集中实现 `SunoOfficialMusicProvider`；兼容合同变化集中修改 `SunoCompatibilityMusicProvider` |
| `backend/app/core/config.py` | Suno、队列和存储环境配置 | 仅在正式合同确实需要新配置时增加字段；不得放真实值 |
| `.env.example` | 后端环境变量模板 | 与 `config.py` 同步新增配置名和无秘密示例 |
| `backend/tests/test_suno_compatibility.py` | 兼容 Provider 的请求、响应、额度和错误测试 | 修改兼容适配时必须同步扩充 |
| `backend/tests/test_music.py` | 任务、额度、重试、人工验证、试听与下载测试 | Provider 行为或状态变化时补回归测试 |

官方实现建议新建：

```text
backend/tests/test_suno_official.py
```

使用 `httpx.MockTransport` 或项目现有测试替身验证正式合同，不要让自动测试真实
消耗 Suno 额度。

### 4.2 只在合同变化时修改

| 文件 | 作用 | 修改条件 |
|---|---|---|
| `backend/app/api/v1/routes/music.py` | `/api/v1/music` 路由、Provider 状态和管理员额度刷新 | 官方状态字段或管理接口确实变化时 |
| `backend/app/schemas/music.py` | 前后端请求与响应 Schema | 对外结构需要新增稳定字段时 |
| `backend/app/models/music.py` | 音乐任务、结果、设置和额度快照 | 必须持久化新的业务字段时；随后必须写 Alembic 迁移 |
| `backend/app/services/music.py` | 任务创建、执行、重试、状态与结果持久化 | 统一 Provider 输出无法表达正式合同所需语义时 |
| `backend/app/services/music_storage.py` | 安全下载、本地/S3 存储 | 官方返回的音频获取方式变化时 |
| `backend/app/services/music_queue.py` | Redis 队列、延迟重试、并发与限频 | 通常不修改 |
| `backend/app/services/task_recovery.py` | 重启后恢复未完成任务 | 任务恢复规则变化时 |
| `backend/app/workers/music.py` | 独立 worker 进程入口 | 通常不修改 |
| `backend/tests/test_workflows.py` | 自动流程把歌词产出传入音乐步骤 | 音乐步骤入参或暂停规则变化时 |

### 4.3 前端位置

| 文件 | 作用 | 修改条件 |
|---|---|---|
| `frontend/src/api/music.ts` | 音乐 HTTP 请求封装 | 后端公开 API 合同变化时 |
| `frontend/src/types/api.ts` | 前端音乐类型 | Schema 变化时同步 |
| `frontend/src/pages/MusicPage.tsx` | 音乐创作、状态、额度、试听、下载和续写页面 | 新增用户可见能力时 |
| `frontend/src/pages/WorkflowsPage.tsx` | 自动流程配置和运行历史 | 工作流音乐参数变化时 |
| `frontend/src/components/WorkflowStepOutputDrawer.tsx` | 当前页查看自动流程音乐产出 | 音乐结果展示字段变化时 |

不要为了底层 Suno 字段变化直接把供应商原始 JSON 泄漏到前端。先在 adapter 和
Schema 中归一化。

### 4.4 数据库迁移

当前相关迁移：

```text
backend/alembic/versions/f31a8c72d604_add_suno_music_tasks_and_results.py
backend/alembic/versions/a91f6c2d3e40_add_music_provider_queue_and_quota.py
backend/alembic/versions/b7d29e4f16c1_add_user_music_task_quota.py
```

如果增加数据库字段，必须创建新的 Alembic migration，不能修改已经执行过的旧
迁移文件。

## 5. 统一 Provider 合同

文件：
`D:\SunJX\projects\blue-music-platform\backend\app\adapters\music_generation.py`

蓝乐业务层依赖以下稳定接口：

```python
class MusicGenerationProvider(Protocol):
    name: str
    implementation: Literal["official", "compatibility"]
    model: str | None

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...
    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...
    def resume(
        self,
        payload: MusicGenerationInput,
        external_task_id: str,
    ) -> MusicGenerationOutput: ...
    def get_quota(self) -> MusicProviderQuota: ...
```

输入 `MusicGenerationInput` 已包含：

```text
title
lyrics
style_prompt
instrumental
negative_tags
requirements
style_tags
source_external_id
```

输出必须归一为：

```text
MusicGenerationOutput
  external_task_id     外部任务稳定编号，得到后立即持久化
  provider_status      统一状态
  tracks[]             一首或多首结果
  call                 ProviderCallMetadata 调用审计

MusicTrackOutput
  external_id
  title
  audio_url
  media_type
  duration_seconds
  image_url
  provider_page_url
```

每次外部调用都要填 `ProviderCallMetadata`，至少记录方法、端点、供应商请求编号、
开始/结束时间、耗时、尝试次数和可获得的计费单位。不得记录认证头、Cookie 或完整
敏感请求体。

## 6. 官方 API 的明确缺口与修改方案

当前 `SunoOfficialMusicProvider` 只有配置检查，以下四个方法都会返回：

```text
SUNO_API_CONTRACT_PENDING
```

需要 Kimi 在拿到正式文档后完成：

1. `generate`：把蓝乐统一输入映射到官方生成请求，取得任务编号后立即触发
   `on_submitted` 持久化。当前 factory 已接收该回调，但官方构造器尚未接收，
   需要给 `SunoOfficialMusicProvider.__init__` 增加回调并在 `get_music_provider`
   创建官方实现时传入。
2. `extend`：使用 `source_external_id` 调用官方续写/延长能力。
3. `resume`：根据已有 `external_task_id` 查询同一任务，不能重复创建。
4. `get_quota`：映射官方余额、已用量、总额度和计费周期；官方无此接口时应明确
   返回“不支持”，不能虚构余额。
5. 认证：严格按官方文档设置请求头；密钥只从环境变量读取。
6. 幂等：如官方支持 idempotency key，应使用蓝乐任务稳定编号；超时后先查询原
   任务，避免重复扣费。
7. 状态：把排队、生成中、完成、部分失败、失败和取消映射到蓝乐稳定语义。
8. 错误：映射 400、401/403、402/额度不足、404、409、429、5xx、连接超时和
   生成超时；读取并保留安全的供应商请求编号与 `Retry-After`。
9. 结果：至少归一化音频编号、标题、音频 URL、媒体类型、时长、封面和官方页面
   URL；任意一首明确失败时不得静默伪装为全部成功。
10. `routes/music.py` 的官方 `provider-status`：联调完成后把
    `contract_pending` 改成能够真实反映配置和连接状态的逻辑。

如果官方 API 使用 webhook，可以新增 webhook 路由，但必须校验官方签名、保证
重复回调幂等，并继续以数据库任务状态为准。不要因此绕过现有 worker；worker 可
负责提交、等待回调超时后的补偿查询和结果归档。

## 7. GitHub 兼容实现的位置与修改方案

### 7.1 隔离服务源码

| 文件 | 作用 |
|---|---|
| `D:\DevTools\SunoCompat\src\lib\SunoApi.ts` | 上游私有网页接口客户端、登录会话、生成、续写、查询和额度 |
| `D:\DevTools\SunoCompat\src\compat-server.ts` | 蓝乐使用的轻量 HTTP 边界、内部鉴权、参数校验和安全错误响应 |
| `D:\DevTools\SunoCompat\package.json` | 依赖与 `build:compat`/`start:compat` 脚本 |
| `D:\DevTools\SunoCompat\tsconfig.compat.json` | 轻量兼容服务的 TypeScript 构建配置 |
| `D:\DevTools\SunoCompat\.env.example` | 上游配置名参考，不包含实际值 |
| `D:\DevTools\SunoCompat\.env.local` | 本机真实秘密配置，禁止读取后输出或提交 |
| `D:\DevTools\SunoCompat\scripts\set-suno-cookie.ps1` | 隐藏输入本机登录会话的脚本 |

不要直接编辑：

```text
D:\DevTools\SunoCompat\compat-dist\
D:\DevTools\SunoCompat\.next\
D:\DevTools\SunoCompat\node_modules\
```

这些是生成物或安装目录。修改 `src` 后通过构建重新生成。

### 7.2 蓝乐当前真正依赖的兼容合同

```text
GET  /api/health
POST /api/custom_generate
POST /api/extend_audio
GET  /api/get?ids=<逗号分隔的音频编号>
GET  /api/get_limit
```

轻量服务当前未提交改动还暴露了 `/api/clip`、`/api/get_aligned_lyrics`、
`/api/persona`、`/api/generate`、`/api/generate_lyrics`、`/api/concat` 和
`/api/generate_stems`。这些路由目前不是蓝乐 P7 主调用链的必需项。保留它们时
仍必须经过 `INTERNAL_API_TOKEN`、请求体限制和统一错误处理；不要仅因上游存在就
让前端或 Agent 直接调用。

### 7.3 兼容服务的修改落盘规则

`D:\DevTools\SunoCompat` 在 `D:\SunJX` 之外。只修改本机克隆会导致换电脑或部署
后丢失，因此完成兼容服务改动后必须同时更新：

```text
D:\SunJX\projects\blue-music-platform\integrations\suno-compat\README.md
D:\SunJX\projects\blue-music-platform\integrations\suno-compat\install.ps1
D:\SunJX\projects\blue-music-platform\integrations\suno-compat\configure-local.ps1
D:\SunJX\projects\blue-music-platform\integrations\suno-compat\0001-Add-isolated-Blue-Music-compatibility-runtime.patch
```

推荐流程：先在 `D:\DevTools\SunoCompat` 的独立分支中整理并提交适配，再用固定
上游提交重新验证补丁可应用；最后把可复现补丁复制回主仓库 integration 目录。
保留上游来源和 LGPL 许可证说明。

### 7.4 人机验证完整闭环（Kimi 必做）

Kimi 必须完整审计上游项目中所有与人机验证有关的触发位置、返回字段、异常和
会话行为，并在蓝乐中补齐**人工验证的完整生命周期**，不能只处理生成提交时的
一个错误字符串。当前实现检查 Suno 是否要求 hCaptcha。若需要验证，兼容服务
返回明确错误，蓝乐将任务置为等待管理员处理：

```text
SUNO_HUMAN_VERIFICATION_REQUIRED
-> provider_status = waiting_human_verification
-> 管理员在正常 Suno 页面完成验证并更新隔离会话
-> POST /api/v1/music/tasks/{task_id}/human-verification-complete
-> 原任务重新入队并继续
```

必须实现并验收以下全部内容：

1. **触发检测**：审计 `D:\DevTools\SunoCompat\src\lib\SunoApi.ts` 中验证码
   检查、生成提交、续写和轮询路径；无论验证要求出现在 HTTP 状态、响应 JSON、
   任务级错误还是单首结果错误中，都归一为
   `SUNO_HUMAN_VERIFICATION_REQUIRED`。
2. **兼容服务响应**：`src/compat-server.ts` 必须返回稳定 HTTP 状态、错误码和
   可安全展示的提示，不返回 HTML 堆栈，不泄漏 Cookie、认证头或上游敏感响应。
3. **任务持久化**：蓝乐保存 `error_code`、安全错误详情、任务编号、已有外部任务
   编号和 `provider_status=waiting_human_verification`。刷新网页、后端重启或
   worker 重启后仍能识别该任务正在等待人工处理。
4. **停止自动重试**：人机验证不是普通 429 或 5xx。worker 检测到后立即停止
   自动重试和轮询，不占用并发槽，不形成持续请求，也不重复扣员工额度。
5. **管理员提示**：`frontend/src/pages/MusicPage.tsx` 应向超级管理员明确展示需要
   在正常 Suno 网页完成验证、随后更新本机会话；普通成员只能看到任务正在等待
   管理员处理，不能看到会话配置和任何凭证。
6. **会话更新**：继续使用
   `D:\DevTools\SunoCompat\scripts\set-suno-cookie.ps1` 的隐藏输入方式更新会话。
   Cookie 只进入隔离服务本机秘密环境，不进入蓝乐数据库、前端、日志或 Git。
7. **恢复原任务**：管理员完成验证后，通过
   `POST /api/v1/music/tasks/{task_id}/human-verification-complete` 恢复任务。
   如果已有外部任务编号，优先查询原任务；只有确认上游从未接受请求时才能重新
   提交，避免重复生成和重复扣费。
8. **权限与幂等**：恢复接口只能由超级管理员调用。重复点击恢复不能重复入队、
   重复提交或重复扣额度；任务不是等待验证状态时返回稳定冲突错误。
9. **会话异常**：缺少 Cookie、Cookie 过期、Suno 401/403 和再次要求验证必须
   分别映射为 `SUNO_COOKIE_NOT_CONFIGURED`、`SUNO_SESSION_EXPIRED` 或
   `SUNO_HUMAN_VERIFICATION_REQUIRED`，并给出不同的管理员处理提示。
10. **状态检查**：`GET /api/health` 和蓝乐 `/api/v1/music/provider-status` 应只
    返回 `captcha_mode`、`cookie_configured`、运行状态和安全提示，不返回 Cookie
    内容。`ready` 只表示服务与普通会话已配置，不承诺下一次生成不会触发验证。
11. **审计信息**：记录任务状态变化、发生阶段、尝试次数、管理员恢复操作和安全
    的供应商请求编号；所有日志经过敏感信息清理。
12. **自动流程联动**：自动流程遇到人机验证时停止在当前音乐步骤，清楚显示等待
    管理员，不得把下游步骤标记成功；恢复并生成完成后才能继续流程。

必须增加或补齐以下自动测试：

- 生成提交时要求验证。
- 续写提交时要求验证。
- 轮询响应和单首结果中出现验证错误。
- 缺少会话、会话过期和 401/403 的不同映射。
- 验证状态不自动重试，worker 重启后仍保持等待。
- 非管理员调用恢复接口返回 403。
- 管理员重复点击恢复保持幂等。
- 已有外部任务编号时恢复只查询原任务。
- 恢复成功不重复扣员工额度。
- 日志、状态接口和错误响应不包含 Cookie、Key 或内部 Token。
- 自动流程在验证时暂停，恢复成功后继续。

不要把验证码自动代答、浏览器指纹伪装或反检测代码纳入蓝乐交付。这里要求
“全部实现”的范围，是上面列出的检测、暂停、通知、会话更新、权限控制、恢复、
幂等、审计和测试闭环。正常情况下的提交、轮询和下载仍应保持自动化。

## 8. 配置名称

蓝乐后端现有配置名如下，只能传递名称，不能传递当前值：

```text
SUNO_PROVIDER_IMPLEMENTATION
SUNO_API_BASE_URL
SUNO_API_KEY
SUNO_MODEL
SUNO_COMPAT_ENABLED
SUNO_COMPAT_BASE_URL
SUNO_COMPAT_SHARED_TOKEN
SUNO_COMPAT_MODEL
SUNO_COMPAT_ALLOW_REMOTE
SUNO_REQUEST_TIMEOUT_SECONDS
SUNO_GENERATION_TIMEOUT_SECONDS
SUNO_POLL_INTERVAL_SECONDS
SUNO_DOWNLOAD_TIMEOUT_SECONDS
SUNO_MAX_AUDIO_BYTES
SUNO_QUOTA_REFRESH_INTERVAL_SECONDS
MUSIC_QUEUE_MODE
MUSIC_QUEUE_NAME
MUSIC_MAX_CONCURRENCY
MUSIC_MIN_REQUEST_INTERVAL_SECONDS
MUSIC_MAX_RETRIES
MUSIC_RETRY_BASE_SECONDS
MUSIC_RETRY_MAX_SECONDS
MUSIC_WORKER_RESERVE_SECONDS
MUSIC_STORAGE_BACKEND
MUSIC_STORAGE_DIR
MUSIC_S3_ENDPOINT_URL
MUSIC_S3_BUCKET
MUSIC_S3_REGION
MUSIC_S3_ACCESS_KEY
MUSIC_S3_SECRET_KEY
MUSIC_S3_PREFIX
MUSIC_S3_PRESIGN_SECONDS
```

隔离服务使用的主要配置名：

```text
COMPAT_HOST
COMPAT_PORT
INTERNAL_API_TOKEN
SUNO_COOKIE 或 SUNO_COOKIE_BASE64
```

真实值存在 `.env`、`.env.local` 或进程环境中。不要执行会把整个环境打印出来的
命令，也不要把凭证放进测试快照、异常 detail、截图或提交。

## 9. 已完成且必须保留的系统能力

- Redis 待处理、处理中和延迟重试队列。
- 独立 music worker，不在 FastAPI 请求线程里长时间生成音乐。
- 全局并发限制，默认 `1`。
- 新生成/续写启动间隔，默认 `30` 秒。
- 429、5xx、网络和生成超时的有界指数退避。
- 401/403、额度不足、参数错误和人工验证不盲目自动重试。
- 外部任务编号一旦获得即落库，进程重启后继续查询原任务。
- 员工音乐任务次数额度；新生成和续写各扣一次，worker 重试不重复扣。
- 管理员可看的供应商真实额度快照。
- 本地或 S3-compatible 音频归档、试听、单独下载和续写。
- 下载器对地址、重定向、媒体类型和文件大小的安全限制。
- 稳定 `error_code`、任务编号、供应商请求编号和安全诊断信息。
- `official`/`compatibility` 选择在任务创建时固化，切换只影响新任务。

不要在修 Provider 时重写这些层。确需修改时，必须说明现有设计为什么无法满足
正式合同，并增加对应回归测试。

## 10. 本地运行与验证

### 10.1 基础设施

```powershell
cd D:\SunJX\projects\blue-music-platform
docker compose up -d postgres redis
docker compose ps
```

### 10.2 后端

```powershell
cd D:\SunJX\projects\blue-music-platform\backend
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 10.3 音乐 worker

```powershell
cd D:\SunJX\projects\blue-music-platform\backend
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m app.workers.music
```

### 10.4 前端

```powershell
cd D:\SunJX\projects\blue-music-platform\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

### 10.5 隔离兼容服务

```powershell
cd D:\DevTools\SunoCompat
D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd run build:compat
D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd run start:compat
```

不要输出 `.env.local`。需要更新普通 Suno 登录会话时，使用现有隐藏输入脚本：

```powershell
cd D:\DevTools\SunoCompat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\set-suno-cookie.ps1
```

健康检查：

```text
http://127.0.0.1:8000/api/v1/health
http://127.0.0.1:8000/api/v1/health/database
http://127.0.0.1:3000/api/health  （需要蓝乐与兼容服务约定的 Bearer Token）
```

## 11. 自动测试命令

### 11.1 兼容服务构建

```powershell
cd D:\DevTools\SunoCompat
D:\DevTools\Node20\node-v20.20.2-win-x64\npm.cmd run build:compat
```

### 11.2 蓝乐后端

```powershell
cd D:\SunJX\projects\blue-music-platform\backend
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m pytest -q
```

当前记忆基线为后端 `87` 项，最终以实际测试输出为准。

### 11.3 蓝乐前端

```powershell
cd D:\SunJX\projects\blue-music-platform\frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

当前记忆基线为前端 `28` 项，最终以实际测试输出为准。

自动测试不得请求真实 Suno 生成。真实生成会消耗额度，必须先得到用户明确确认。

## 12. 最低验收标准

### 12.1 Provider 合同

- 生成、续写、已有任务恢复查询和额度查询均通过统一 Provider。
- 正式或兼容实现切换不需要修改工作流、作词或前端调用入口。
- 新任务保存实际 `provider_implementation` 和模型。
- 外部任务编号收到后立即保存；重试和重启不重复提交。
- 多首结果完整归一化并归档，部分失败不会伪装成全部成功。

### 12.2 错误和重试

- 400、401/403、402/额度不足、404、409、429、5xx、连接超时和生成超时有稳定
  错误码。
- 429 尊重 `Retry-After`；没有该字段时使用现有有界退避。
- 自动重试不重复扣员工额度。
- 人工验证满足第 7.4 节的完整清单，能暂停并恢复同一任务，不会形成无限循环。
- 日志和接口错误不泄漏 Key、Cookie、Bearer Token 或完整敏感请求。

### 12.3 产品行为

- 管理员能看到真实的 Provider 状态和可获得的真实余额。
- 成员只能看到自己被分配的任务次数额度，不看到团队账户凭证。
- 生成结果可试听、单独下载、重新生成和续写。
- 自动流程仍能把歌词版本正确传入音乐步骤，并在失败时真实停止。

## 13. Kimi 完成后必须交回的信息

请给用户或 Codex 返回以下内容，禁止只回复“已经完成”：

1. 修改目的和选择的是 `official`、`compatibility`，还是两者。
2. 蓝乐主仓库的完整修改文件清单。
3. `D:\DevTools\SunoCompat` 的完整修改文件清单和独立提交哈希。
4. 主仓库可复现补丁是否同步更新。
5. 新增依赖、版本、许可证和必要性。
6. 构建、后端测试、前端测试、lint 和 build 的真实结果。
7. 使用 mock 完成的接口场景，以及仍需真实账号验收的场景。
8. 若经用户确认执行真实任务，提供蓝乐任务编号、状态迁移、结果数量和下载验证，
   但不得提供任何凭证。
9. 已知风险、未完成项和安全回滚步骤。
10. 提交哈希；如果 `git pull`、commit 或 push 失败，明确说明原因。

## 14. 推荐阅读顺序

```text
1. D:\SunJX\AGENTS.md
2. D:\SunJX\docs\notes\蓝乐_当前上下文速记.md
3. 本文件
4. D:\SunJX\projects\blue-music-platform\docs\03-implementation\P7_Suno音乐创作维护说明.md
5. D:\SunJX\projects\blue-music-platform\backend\app\adapters\music_generation.py
6. D:\SunJX\projects\blue-music-platform\backend\app\services\music.py
7. D:\SunJX\projects\blue-music-platform\backend\tests\test_suno_compatibility.py
8. D:\SunJX\projects\blue-music-platform\backend\tests\test_music.py
9. D:\DevTools\SunoCompat\src\compat-server.ts
10. D:\DevTools\SunoCompat\src\lib\SunoApi.ts
```

如正式 Suno 文档与本文冲突，以正式文档的字段和认证要求为准，但蓝乐的统一
Provider、队列、持久化、额度、错误透明和 Agent 隔离边界必须保留。
