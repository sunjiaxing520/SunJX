# 蓝乐真实项目视频：首版审阅剪辑

## 最新风格小样

用户最新要求：不要人物漫画，整体仍为第一版文字和页面结构，采用手绘笔记视觉。
曾生成的人物概念图不采用，保存在 D 盘 unused-character-concept，不进入视频或仓库。

`handdrawn-preview.json`、`render-handdrawn.cjs`、`build-handdrawn.py` 生成新的无人物小样。
成片目录：`D:\DevTools\VideoProjects\BlueMusic-AIStory\handdrawn-preview`。
`Handdrawn_Opening_A.mp4` 采用 Yunxia 男声，`Handdrawn_Opening_B.mp4` 采用 Yunjian 男声。
两版约 10 秒，同一口语化文案、同一画面；不添加背景音乐以便比较声音。
`compare.html` 可对比播放，`audio`/`voice-*.wav` 保留单独配音。画面为真实隔离测试截图
加手绘边框与标题，没有把截图转绘为虚构界面。小样不代表完整版已经改完；待用户选声音与风格。

## 原60秒版本

成片：`D:\DevTools\VideoProjects\BlueMusic-AIStory\BlueMusic_AIStory_60s.mp4`

60 秒、1080x1920、30fps、H.264/AAC；无需人物出镜。包含中文合成旁白、烧录字幕、
原始截图轻推近、历史文字摘录和程序合成的轻背景节奏。没有调用蓝乐的业务模型或音乐接口。

## 素材边界

- 图片来自项目 `logs/provider-presets-ui` 的真实 Playwright 隔离测试截图。
- 聊天为本会话历史文字摘录重排，不是原始聊天截图，也不伪造实时打字。
- 180/37 来自 2026-09-08 开发测试记录，以说明卡展示，不伪造终端输出。
- 画面标注隔离测试、历史记录和合成旁白，保留音乐接口尚待真实联调的说明。
- 没有客户真实作品、身份、源码正文、真实密钥、客户使用录像或未授权歌曲。
- 这是截图/文字的首版剪辑，不是完整产品操作录屏版。后续可以用脱敏演示录屏替换相应镜头。
- 发布前用户应确认合同允许公开项目界面，并按发布平台流程声明 AI 合成内容。

## 复现

源文件 `story.json` 定义文字/素材，`render-frames.cjs` 生成画面，`build-video.py` 生成配音、
字幕与 MP4。工具安装在 D 盘 `D:\DevTools\VideoTools\python-packages`，不改项目运行依赖。
Node 使用本机 Playwright 工具库，Python 使用 Codex bundled runtime (Pillow/numpy 已有)。
额外依赖为 imageio-ffmpeg 和 edge-tts。合成服务会收到公开旁白文字，不接收客户数据。
已有旁白文件缓存复用，不重复请求合成。背景节奏由数学波形生成，无采样音乐。

导出目录同时有 `captions.srt`、`narration.wav`、`original-bed.wav`、画面和逐镜时间表。
字幕按短句时长比例对齐，未做逐字强制对齐；真人配音替换后需要重新对齐。
版本控制只保存制作源文件，视频、配音和截图留在 D 盘，不上传仓库。
