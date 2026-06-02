# 蓝乐 AI 音乐创作平台

基于多智能体的 AI 音乐榜单爬取、风格分析与智能创作平台。

## 当前状态

项目资料已整理进入 `SunJX/projects/blue-music-platform`，包含：

- 需求规格说明书：`需求规格说明书_v2.md`
- 报价方案：`报价方案.docx`
- 客户讲解手册：`客户讲解手册.md`
- 实现方向与接口设计：`06_实现方向与接口设计.md`
- 前端静态演示：`demo/agent-console/index.html`
- 后端 FastAPI 雏形：`backend/`
- Docker Compose 雏形：`docker-compose.yml`

目前代码仍处于早期骨架阶段，真正开发应从项目结构、后端基础架构、数据库模型和前端工程化开始。

## 前端演示

当前 demo 独立存放在：

```text
demo/agent-console/index.html
```

演示定位：

```text
第一阶段：人操作多个 Agent
后续升级：总调度 Agent 调用多个专业 Agent
```

## 产品目标

平台核心链路：

```text
音乐榜单采集 -> 音乐特征分析 -> AI 辅助创作 -> Dashboard 展示 -> 权限与审计管理
```

## 技术栈

- 后端：FastAPI
- 前端：React + TypeScript + Ant Design
- 数据库：PostgreSQL
- 缓存/任务：Redis
- 部署：Docker Compose

## 推荐推进顺序

1. 整理项目工程结构。
2. 完成后端配置、数据库连接和健康检查。
3. 建立用户、角色、权限、Agent、歌曲、分析结果、创作记录等核心模型。
4. 实现登录注册和 JWT 鉴权。
5. 实现 Agent 配置与状态管理。
6. 实现爬虫 Agent 的手动触发和数据入库。
7. 实现分析 Agent 和创作 Agent。
8. 完成 Dashboard、部署文档和验收清单。

## 协作要求

所有 agent 修改本项目之前必须先阅读仓库根目录的 `AGENTS.md`。
