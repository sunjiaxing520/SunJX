# 一件 · YIJIAN

把目标拆成今天可以完成的小事。中文学习计划与待办网页版，React + TypeScript + FastAPI + PostgreSQL，Docker Compose 自托管。

## 已实现

- **基础模式**：无需 AI Key，注册账号即可使用计划、待办、子任务、优先级、日历、完成记录、实际用时与掌握情况。
- **AI 模式**：在设置中接入自己的 Kimi Key，与 AI 商议目标，查看任务变更草稿，确认后写入清单，再通过聊天微调。支持撤销最近一次 AI 调整；后续已有修改时禁止覆盖式撤销。
- 自定义计划名称；考研、考公、专升本、私人学习、日常清单五类。私人学习期限可选。
- 同账号电脑与手机共享服务器数据。页面每 7 秒及重新聚焦时刷新，聊天每 8 秒刷新；并发写入通过 revision 冲突检查保护。
- 今天、我的计划、周/月日历、学习复盘、设置。桌面 AI 侧栏、手机全屏聊天、底部导航、局部毛玻璃。
- JSON 导出与计划/任务恢复。导出含聊天；当前 JSON 导入不恢复聊天、密钥或账号。

## Docker 启动

需要 Docker Compose、Python 3（仅用于生成配置）。在本目录执行：

```sh
python scripts/setup.py
docker compose up -d --build
```

打开 http://localhost:4175 并创建自己的账号。每个账号的 AI 默认关闭，在设置中添加 Key 后开启。手机与电脑连接同一网络，访问电脑的局域网 IP 加 `:4175`，登录同一个账号。需要电脑运行 Docker、网络可达且防火墙允许该端口。

容器应用端口 4175，数据库管理端口仅绑定本机 55475。数据库使用独立 `postgres_data` 卷。`docker compose stop` 停止服务，`docker compose up -d` 恢复；不要用 `down -v`，它会删除数据库卷。

部署到远程服务器后可以跨网络同步；正式公网服务应配置 HTTPS 反向代理，并在 `.env` 中设置 `COOKIE_SECURE=true`。本仓库没有自动发布公网服务。

## 开发

需要 Node.js 22.12+、Python 3.12。生成 `.env` 并启动数据库后：

```sh
docker compose up -d db
python -m venv .venv
# 激活 .venv 后执行；Windows 为 .venv/Scripts/Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8175 --reload
```

另一个终端：

```sh
npm ci
npm run dev
```

Vite 4175 同源代理 `/api` 到 8175；先停止 Compose 的 app，避免端口冲突。也可 `npm run build` 后直接由 FastAPI 提供前端。无 DATABASE_URL 时仅开发使用本地 SQLite，不能与 PostgreSQL 数据混用。

## 测试

```sh
npm run build
python -m pytest tests -q
node tests/browser-smoke.cjs
```

浏览器测试需要本机 Edge 和运行中的服务，默认 `http://127.0.0.1:4175`，可用 `TODO_URL` 覆盖。它创建独立测试账号，不调用 AI。检查注册、无 Key 待办、两浏览器同步、手机编辑、320/390/768/1440 宽度的五个页面。

`tests/kimi-live.cjs` 是开发者显式启用的真实供应商联调，不在默认测试中运行；会消耗 API 额度，要求本地忽略目录中的开发账号文件。

## 数据与安全

密码用 Argon2 哈希，会话采用 HttpOnly Cookie；Key 按账号用 Fernet 加密，只在服务端调用固定的 Kimi 官方 API。不会下发 Key，也不会让其他用户借用你的 Key。启用 AI 时会把当前计划、相关任务与最近对话发送给 Kimi。

`.env`、`.runtime/`、数据库及账号文件不进入 Git。务必备份 `.env` 的 ENCRYPTION_KEY：丢失后已有 Key 无法解密。数据库完整备份可运行 `python scripts/backup.py`；备份写入忽略目录 `.runtime/backups/`，应另存到安全位置。恢复建议在新的独立数据库中使用 `pg_restore`，确认后再切换连接。

这是第一版自托管应用：没有离线编辑、系统推送、找回密码或后台自动督学。复盘依赖实际勾选和填写的数据；AI 为按需聊天。当前采用单用户 JSON 状态及乐观锁，适合个人和小规模使用；横向扩容前需要共享限流、细粒度数据模型和正式迁移流程。首次启动自动建表，已有表结构升级不能替代数据库迁移。

## 代码

- `src/main.tsx`：页面、任务与计划编辑、AI 对话。
- `src/styles.css`：设计与响应式布局。
- `backend/main.py`：账号、状态、AI 设置、聊天及草稿接口。
- `backend/ai.py`：Kimi 请求和变更校验。
- `backend/db.py` / `schemas.py`：持久化与输入约束。
- `Dockerfile` / `compose.yaml`：独立运行环境。

许可证：MIT。产品名暂定，可后续调整。
