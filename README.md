# SunJX Workspace

这是 SunJX 的正式工作区，用于集中管理项目代码、文档、素材、工具和备份。

## 目录结构

```text
SunJX/
├─ projects/                 # 正式项目代码仓库
├─ docs/                     # 需求、记录、决策和项目文档
│  ├─ requirements/          # 需求文档
│  ├─ notes/                 # 日常记录
│  └─ decisions/             # 重要技术/产品决策
├─ assets/                   # 图片、音频、视频等素材
│  ├─ images/
│  ├─ audio/
│  └─ video/
├─ tools/                    # 辅助工具、快捷方式、脚本
│  └─ shortcuts/
└─ archive/                  # 历史资料和手动备份
   └─ manual-backups/
```

## 版本管理建议

压缩包可以作为手动备份，但不建议作为主要版本管理方式。

推荐组合：

- Git：记录项目的每次正式改动。
- 远程仓库：把项目同步到 GitHub、Gitee 或 GitLab。
- 压缩包：只作为阶段性离线备份，例如每周或每个里程碑保存一次。

## 工作习惯

- 新项目放入 `projects/`。
- 需求和想法先写入 `docs/requirements/` 或 `docs/notes/`。
- 图片、音频、视频等素材放入 `assets/`。
- 快捷方式、辅助脚本和工具放入 `tools/`。
- 不再使用的旧资料放入 `archive/`。
