# 人机验证处理与回退记录

记录日期：2026-08-11

## 结论

已审阅 `blue_music_suno_captcha_modification_archive.md`。其中涉及 2Captcha、浏览器自动化、反检测参数、鼠标轨迹模拟和自动提交 hCaptcha 的内容未实施，也未安装相关依赖或写入任何密钥配置。

兼容服务继续使用现有的人工验证流程：当 Suno 要求人机验证时，服务返回 `SUNO_HUMAN_VERIFICATION_REQUIRED`；管理员在正常的 Suno 网页中完成验证并更新本机隔离会话后，再将任务重新入队。

## 本次实际变更

- 未修改 `src/lib/SunoApi.ts`。
- 未修改 `src/lib/utils.ts`。
- 未修改 `src/compat-server.ts` 的现有人工验证状态。
- 未修改 `package.json`、锁文件或浏览器依赖。
- 未修改 `.env.example` 或 `.env.local`。
- 新增本文件，作为本次处理和回退依据。

## 当前行为

1. 生成前检查 Suno 是否需要人机验证。
2. 未要求验证时，按原流程继续生成。
3. 要求验证时，返回稳定错误码 `SUNO_HUMAN_VERIFICATION_REQUIRED`。
4. 蓝乐 Worker 将任务保持为等待人工验证状态；验证完成后可重试，不伪造成功结果。

## 人工处理步骤

1. 管理员使用正常浏览器登录 Suno 并按网页提示完成验证。
2. 在本机隔离服务中更新登录会话，使用既有的隐藏输入脚本，不在代码、文档或日志中保存 Cookie、Token 或 API Key。
3. 重启隔离服务。
4. 在蓝乐中重新入队等待人工验证的任务。

## 回退步骤

本次没有源代码、依赖或环境配置变更，因此无需执行代码回退。

如后续有人错误地加入了自动验证码处理，请按以下顺序恢复到本记录对应状态：

1. 停止兼容服务。
2. 删除自动验证码相关依赖、环境变量和辅助文件，不要删除现有人工验证错误处理。
3. 将 `captcha_mode` 保持为 `human_verification`。
4. 还原 `getCaptcha()` 为“无需验证返回 `null`，需要验证时抛出人工验证错误”的行为。
5. 重新安装依赖、执行构建，并启动兼容服务。
6. 确认健康接口没有泄露凭据，且人机验证错误仍映射为 `SUNO_HUMAN_VERIFICATION_REQUIRED`。

## 验证记录

- 未运行构建或测试，因为本次没有修改运行代码、依赖或配置。
- 本记录不包含任何 Cookie、Token、API Key 或账户信息。

---

## 2026-08-18 反转记录：恢复自动人机验证

经用户明确授权，本文件此前"不实施自动代答"的结论正式反转：

- 已恢复上游 `getCaptcha()` 完整求解链路（rebrowser-playwright、2Captcha 坐标求解、
  可选 ghost-cursor）及上游请求头；依赖 `@2captcha/captcha-solver`、
  `rebrowser-playwright-core`、`@playwright/browser-chromium`、
  `ghost-cursor-playwright`、`user-agents`、`yn` 已加入 `package.json`。
- 新增兜底：`TWOCAPTCHA_KEY` 未配置时，`getCaptcha()` 仍抛出人工验证错误，映射为
  `SUNO_HUMAN_VERIFICATION_REQUIRED`，本文件第"人工处理步骤"节继续有效。
- 实测依据：恢复上游请求头前，生成接口返回误导性 403"无模型权限"；恢复后确认为
  真实 hCaptcha 拦截（409），人工验证无法支撑常态化生成。
- 2Captcha Key 只写入本机 `.env.local`，不进入 Git、日志或聊天。
- 回退方向：如需回到纯人工验证，清空 `.env.local` 中的 `TWOCAPTCHA_KEY` 并重启服务
  即可，无需改代码。
