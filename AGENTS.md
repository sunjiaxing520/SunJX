# Agent Instructions

本仓库由多个 agent 协作维护。所有 agent 必须遵守以下规则。

## Git Sync Workflow

开始修改前，先检查状态并同步云端：

```bash
git status
git pull
```

修改完成后，必须保存版本并上传云端：

```bash
git status
git add .
git commit -m "Describe the change"
git push
```

如果 `git pull` 或 `git push` 失败，必须明确告诉用户失败原因，不要假装已经同步完成。

除非用户明确说“不要提交”或“不要上传”，否则完成修改后必须 commit 并 push。

## Safety Rules

- 不要删除、覆盖、回滚用户或其他 agent 的改动，除非用户明确要求。
- 不要修改和当前任务无关的文件。
- 每次改动要保持聚焦，提交说明要清楚说明本次做了什么。
- 如果遇到 Git 冲突，先停止并向用户说明冲突文件和原因。

## Recommended Commit Message

提交说明使用简短、具体的人话，例如：

```bash
git commit -m "Add workspace agent instructions"
git commit -m "Update project documentation"
git commit -m "Initialize music platform project"
```
