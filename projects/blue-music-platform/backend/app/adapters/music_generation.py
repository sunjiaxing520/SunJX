from dataclasses import dataclass
from typing import Protocol

from app.adapters.text_generation import ProviderCallMetadata
from app.core.config import settings


class MusicProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "SUNO_PROVIDER_FAILED",
        call: ProviderCallMetadata | None = None,
        detail: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.call = call
        self.detail = detail


@dataclass(frozen=True)
class MusicGenerationInput:
    title: str
    lyrics: str
    style_prompt: str
    instrumental: bool
    negative_tags: list[str]
    requirements: str | None
    source_external_id: str | None = None


@dataclass(frozen=True)
class MusicTrackOutput:
    external_id: str
    title: str
    audio_url: str
    media_type: str = "audio/mpeg"
    duration_seconds: int | None = None
    image_url: str | None = None
    provider_page_url: str | None = None


@dataclass(frozen=True)
class MusicGenerationOutput:
    external_task_id: str
    provider_status: str
    tracks: list[MusicTrackOutput]
    call: ProviderCallMetadata


class MusicGenerationProvider(Protocol):
    name: str
    model: str | None

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...


class SunoOfficialMusicProvider:
    name = "suno"

    def __init__(self) -> None:
        self.model = settings.SUNO_MODEL or None
        if not settings.SUNO_API_BASE_URL or not settings.SUNO_API_KEY:
            raise MusicProviderError(
                "尚未配置 Suno 官方 API。请先在 Suno Platform 获得正式访问权限和密钥",
                code="SUNO_API_NOT_CONFIGURED",
                detail={"platform_url": "https://platform.suno.com/"},
            )

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        raise self._contract_pending()

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        raise self._contract_pending()

    @staticmethod
    def _contract_pending() -> MusicProviderError:
        return MusicProviderError(
            "Suno 官方 API 账号已配置，但正式接口合同尚未完成联调",
            code="SUNO_API_CONTRACT_PENDING",
            detail={"platform_url": "https://platform.suno.com/"},
        )


def get_music_provider() -> MusicGenerationProvider:
    return SunoOfficialMusicProvider()
