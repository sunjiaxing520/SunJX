# Git 和 Agent 使用备忘

日期：2026-06-02

## 这个工作区是什么

本地工作区：

```text
C:\Users\Administrator\Desktop\SunJX
```

GitHub 云端仓库：

```text
https://github.com/sunjiaxing520/SunJX
```

本地负责日常修改，Git 负责记录版本，GitHub 负责云端备份。

## 我自己常用的 Git 命令

查看当前状态：

```bash
git status
```

从 GitHub 下载最新内容：

```bash
git pull
```

保存当前修改：

```bash
git add .
git commit -m "说明这次改了什么"
```

上传到 GitHub：

```bash
git push
```

查看历史版本：

```bash
git log --oneline
```

## 日常最简单流程

开始修改前：

```bash
git status
git pull
```

修改完成后：

```bash
git status
git add .
git commit -m "说明这次改了什么"
git push
```

## 对其他 agent 的要求

以后让任何 agent 操作这个仓库时，可以直接说：

```text
先阅读 AGENTS.md，严格遵守：
修改前先 git status 和 git pull；
修改后必须 git add、git commit、git push；
如果 pull 或 push 失败，必须明确告诉我原因。
```

## 重要规矩

- 修改之前先下载云端最新内容。
- 修改之后记得上传到 GitHub。
- 不允许只改本地不上传，除非我明确说“不要提交”或“不要上传”。
- 不允许删除、覆盖、回滚用户或其他 agent 的改动，除非我明确要求。
- 如果遇到冲突，要先停下来说明，不要自己乱合并。

## 怎么判断当前状态好不好

如果运行：

```bash
git status
```

看到：

```text
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

说明：

```text
本地和 GitHub 已同步，没有遗漏修改。
```
