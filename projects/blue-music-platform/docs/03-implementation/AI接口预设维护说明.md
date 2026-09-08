# AI 接口预设维护说明

更新：2026-09-08

## 当前交互

管理员在 AI 接口页面点击新建，选择供应商并填写 API Key；名称、模型、地址和协议参数
按模板自动填写。重复供应商自动在名称后加序号，高级配置默认折叠，仍可修改全部参数。
通用 OpenAI 兼容模板没有通用地址和模型，因此自动展开高级配置，需自行填写。
切换模板清空刚输入的密钥，关闭弹窗也清空；编辑现有配置不回显明文密钥。
提供“仅保存”和“保存并测试”；后者先保存、再测试，失败也保留配置，不重复创建。
结果显示在页面顶部，成功后明确点击并确认启用；不自动切换供应商。
测试会产生少量真实调用用量，按钮提示说明；列表失败原因可展开，支持手机页面。
成员不能创建、修改或启用接口。数据库密文存储与热切换机制保持不变。

## 供应商

现有 Kimi、智谱、DeepSeek、阿里百炼、MiniMax 模板保留；新增 Google Gemini。
Gemini 默认 `gemini-2.5-flash`，地址为
`https://generativelanguage.googleapis.com/v1beta/openai`。
复用 JSON 请求、错误分类、重试、Token 统计；仅 Google 官方域名下 2.5 Flash/Flash-Lite
设置 `reasoning_effort=none`，避免短连接测试的输出预算被思考占用，不影响其他模型。
来源：[Google 官方兼容文档](https://ai.google.dev/gemini-api/docs/openai)。
Google API 的网络可达性、账号地域资格、额度及模型访问权限仍需真实 Key 测试。
尚未使用真实 Gemini Key 联调，不能把模板存在当作供应商验收通过。

## 文件与验证

- `backend/app/core/ai_provider_templates.py`：模板单一来源，后端补全默认值。
- `backend/app/adapters/text_generation.py`：共用文本调用及供应商参数差异。
- `frontend/src/pages/AiProvidersPage.tsx`：简化新增弹窗与高级参数。
- `backend/tests/test_ai_providers.py`：新增 Gemini 仅 Key 创建、密钥不回显及请求契约测试。
- `scripts/check-provider-presets-ui.cjs`：浏览器隔离测试；无真实 API 提交。

后端全量 180 项通过，前端 37 项通过，lint/build 通过；Playwright 1440/390px
验证仅 Key 提交、默认参数、切模板清空密钥、重开弹窗清空和通用模板展开。
截图保存在 Git 忽略的 `logs/provider-presets-ui`。

## 配置与测试一致性

更换供应商或归一化后的接口地址必须重新填写 Key，禁止跨地址保留旧密钥；仅改名称或
模型可以保留。同一供应商切换无需代码或服务重启。后端只传新模板时也使用新模板默认
地址、模型和协议参数，不沿用旧地址。

配置增加 `config_revision`，每次编辑递增；测试保存结果使用数据库条件更新匹配版本，
版本变化或配置删除返回 409 `AI_PROVIDER_TEST_STALE`。真实调用用量仍记录，旧结果
不写入当前配置。编辑和启用读取时加行锁，防止启用与编辑相互覆盖。
连接测试严格要求返回 `{"status":"ok"}`；任意 JSON 不再算成功。
401/402/403/404/429 提示对应排查方向，429 不武断等同于余额不足。
连接通过不代表完整作词验收；不自动发起收费的业务生成测试。

迁移头 `e91b4d067c23`，本机已应用；迁移前备份
`D:\DevTools\Backups\BlueMusic\before-provider-revision-20260908.dump`。
新增回归：跨地址/供应商缺 Key 拒绝、新供应商默认值、慢测试失效、错误 JSON 拒绝及用量保留。
浏览器隔离测试增加保存后测试失败/成功、仅一次创建、明确确认启用。

## 本机数据修复

Kimi 配置 id=3 的名称原值为 `Kimi ????????????`，确认是数据库字面问号，
不是前端解码问题。仅将该行名称改为 `Kimi 开发测试（上线前更换密钥）`，
保留模型 kimi-k3、密钥密文、当前启用状态及测试状态。修复时用 Unicode 转义传入
命令避免终端编码损坏；不要将任何用户名称中的正常问号批量替换。
后端与独立 music worker 已重启；前端生产包已更新，原公网隧道地址保持不变。
