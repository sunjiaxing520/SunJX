# 蓝乐 AI 音乐创作平台

蓝乐是一个面向音乐创作者的 AI 音乐创作工作台。

当前首期主线：

```text
酷狗榜单采集 -> 音乐分析 -> AI 作词 -> 官方音乐生成 API -> Dashboard 展示
```

## 先看这里

如果你是第一次打开项目，建议按这个顺序看：

1. `中文代码地图.md`：用中文理解每个目录和主要文件。
2. `项目知识图谱.md`：查看文件引用、请求运行和数据库关系。
3. `docs/README.md`：文档导航，说明每类资料放在哪里。
4. `docs/01-current-scope/项目精炼说明.md`：用最短篇幅理解项目。
5. `docs/01-current-scope/需求规格说明书_v2.md`：当前需求和验收边界。
6. `docs/02-decisions/决策记录.md`：以这里记录的最新决策为准。
7. `docs/03-implementation/分阶段开发任务书.md`：开发阶段、交付物和验收标准。
8. `backend/app/main.py`：当前后端入口代码。
9. `frontend/src/main.tsx`：正式前端入口和全局主题配置。

## 目录说明

```text
blue-music-platform/
├── backend/             # FastAPI 后端代码
├── frontend/            # React + TypeScript 正式前端
├── demo/                # 静态演示页面
├── docs/                # 需求、决策、报价、讲解和历史资料
├── docker-compose.yml   # PostgreSQL、Redis、后端服务编排
├── README.md            # 项目开发入口
├── 中文代码地图.md       # 项目目录和代码阅读导航
└── 项目知识图谱.md       # 文件引用和运行路线图
```

## 当前代码状态

项目已完成后端底座、P2 登录权限和 P3 前端工作台阶段：

- 后端已有 FastAPI 入口、健康检查、统一错误追踪和一键诊断。
- Docker Compose 已包含 PostgreSQL、Redis、backend。
- 已实现用户模型、数据库迁移、Argon2 密码哈希、JWT 登录和权限接口。
- 已实现超级管理员初始化、内部成员管理和四类 Agent 权限。
- 已实现真实登录、受保护路由、权限导航、Dashboard、Agent 状态和账号管理页面。
- 已实现前端安全诊断记录，可复制最近错误的 `request_id` 供维护定位。
- 榜单、分析、作词和音乐创作 Agent 业务接口尚未实现。

## 当前有效口径

开发时以这些文件为准：

- `docs/01-current-scope/需求规格说明书_v2.md`
- `docs/01-current-scope/项目精炼说明.md`
- `docs/02-decisions/决策记录.md`

特别注意：

- 首期爬虫数据源是酷狗热歌榜。
- 首期模式是一条固定工作流，内部仍按多个 Agent 模块执行。
- 总调度 Agent、自定义工作链、复杂长期记忆系统都属于后续增强。

## 技术栈

- 后端：FastAPI
- 前端：React + TypeScript + Ant Design
- 数据库：PostgreSQL
- 缓存/任务：Redis
- 部署：Docker Compose

## 推荐开发顺序

1. 后端基础结构、配置、数据库连接。
2. 用户、角色、权限和 JWT 鉴权。
3. Dashboard 工作台基础数据和正式前端。
4. 酷狗榜单采集任务。
5. 音乐分析 Agent。
6. 作词 Agent 和基础记忆。
7. Suno 创作 Agent。
8. 前后端联调、部署文档和验收清单。
