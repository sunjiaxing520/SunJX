# P7 Suno 音乐创作维护说明

更新时间：2026-07-23

## 当前状态

首期供应商锁定为 Suno，只接官方 API。平台内部任务、数据库、页面和工作流基础已完成；Suno Platform 的真实 HTTP 请求仍等待正式文档、API Key 和商用权限。

未配置时必须返回明确失败：

- `SUNO_API_NOT_CONFIGURED`：缺少官方地址或 Key。
- `SUNO_API_CONTRACT_PENDING`：已有配置，但代码尚未按正式文档完成请求与响应映射。

不得通过模拟成功、假音频、非官方套壳、逆向接口或网页自动化绕过该状态。

## 代码路线

```text
frontend/src/pages/MusicPage.tsx
-> POST /api/v1/music/tasks
-> routes/music.py
-> services/music.py
-> adapters/music_generation.py
-> Suno 官方 API
-> music_tasks / music_results / api_usage_records
-> 试听、下载或续写
```

自动流程的数据传递：

```text
ranking snapshot_id
-> analysis report_id
-> lyrics version_id
-> music task_id
-> music result_id
```

## 已实现能力

- 从歌词版本创建完整生成任务。
- 保存标题、歌词、风格、排除标签、纯音乐选项和补充要求。
- 保存外部任务编号、供应商状态、错误码和错误详情。
- 同一任务支持多个独立音乐结果。
- 音频优先归档到 `backend/storage/music`，归档失败时保留安全错误说明。
- 独立试听区、鉴权播放、浏览器下载和来源结果续写。
- 音乐任务单条/批量删除，音乐结果单条删除。
- Suno 调用进入统一用量账本，计量单位按官方响应保存，不伪造 Token。
- 工作流支持“采集 -> 分析 -> 作词 -> 音乐创作”四步传参。

## 正式联调清单

拿到 Suno 官方权限后，按 Platform 文档完成：

1. 确认认证请求头、正式 Base URL、生成和续写路径。
2. 映射提交参数，尤其是歌词、风格、纯音乐和排除标签。
3. 映射异步任务编号、状态枚举、失败字段和多个结果。
4. 实现官方建议的轮询或回调，并遵守并发和频率限制。
5. 验证音频 URL 有效期、最大文件、格式、封面和供应商作品页。
6. 记录官方计费单位、请求编号、耗时和尝试次数。
7. 用中文歌词完成生成、失败、超时、续写、下载和删除验收。

API Key 只能写入本机或服务器 `.env`，禁止进入测试夹具、截图、日志、文档和 Git。

## 测试

```powershell
D:\DevTools\Venvs\blue-music-backend\Scripts\python.exe -m pytest -q
cd D:\SunJX\projects\blue-music-platform\frontend
npm.cmd run test
npm.cmd run lint
npm.cmd run build
```

自动测试使用 `FakeSunoProvider`，只验证平台自身的数据流、状态、归档和删除行为，不冒充真实 Suno 联调。
