from dataclasses import dataclass


@dataclass(frozen=True)
class AiProviderTemplate:
    key: str
    display_name: str
    protocol: str
    description: str
    default_base_url: str
    default_model: str
    requires_api_key: bool
    supports_json_mode: bool
    max_tokens_parameter: str
    console_url: str | None
    docs_url: str | None


AI_PROVIDER_TEMPLATES = (
    AiProviderTemplate(
        key="local",
        display_name="本地规则",
        protocol="local",
        description="不调用第三方接口，适合离线开发、演示和故障降级。",
        default_base_url="",
        default_model="rules-v1",
        requires_api_key=False,
        supports_json_mode=False,
        max_tokens_parameter="max_tokens",
        console_url=None,
        docs_url=None,
    ),
    AiProviderTemplate(
        key="bigmodel",
        display_name="智谱 BigModel",
        protocol="openai_compatible",
        description="智谱开放平台的 OpenAI 兼容文本接口。",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4.7-flash",
        requires_api_key=True,
        supports_json_mode=True,
        max_tokens_parameter="max_tokens",
        console_url="https://bigmodel.cn/",
        docs_url="https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
    ),
    AiProviderTemplate(
        key="deepseek",
        display_name="DeepSeek",
        protocol="openai_compatible",
        description="DeepSeek 官方 OpenAI 兼容文本接口。",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        requires_api_key=True,
        supports_json_mode=True,
        max_tokens_parameter="max_tokens",
        console_url="https://platform.deepseek.com/",
        docs_url="https://api-docs.deepseek.com/",
    ),
    AiProviderTemplate(
        key="qwen",
        display_name="阿里百炼 Qwen",
        protocol="openai_compatible",
        description="阿里云百炼北京地域的 OpenAI 兼容文本接口。",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        requires_api_key=True,
        supports_json_mode=True,
        max_tokens_parameter="max_tokens",
        console_url="https://bailian.console.aliyun.com/",
        docs_url="https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
    ),
    AiProviderTemplate(
        key="minimax",
        display_name="MiniMax",
        protocol="openai_compatible",
        description="MiniMax 的 OpenAI 兼容文本接口。",
        default_base_url="https://api.minimaxi.com/v1",
        default_model="MiniMax-M2.7",
        requires_api_key=True,
        supports_json_mode=False,
        max_tokens_parameter="max_completion_tokens",
        console_url="https://platform.minimaxi.com/",
        docs_url="https://platform.minimaxi.com/docs/api-reference/text-chat-openai",
    ),
    AiProviderTemplate(
        key="openai_compatible",
        display_name="通用 OpenAI 兼容",
        protocol="openai_compatible",
        description="用于其他提供 /chat/completions 的兼容服务或自建模型。",
        default_base_url="",
        default_model="",
        requires_api_key=True,
        supports_json_mode=True,
        max_tokens_parameter="max_tokens",
        console_url=None,
        docs_url=None,
    ),
)

AI_PROVIDER_TEMPLATE_MAP = {
    template.key: template for template in AI_PROVIDER_TEMPLATES
}


def get_ai_provider_template(key: str) -> AiProviderTemplate | None:
    return AI_PROVIDER_TEMPLATE_MAP.get(key)
