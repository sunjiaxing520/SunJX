from app.adapters.music_generation import (
    MusicGenerationInput,
    MusicGenerationOutput,
    MusicTrackOutput,
)
from app.adapters.text_generation import ProviderCallMetadata


class FakeSunoProvider:
    name = "suno"
    model = "suno-test-model"

    def __init__(self) -> None:
        self.generated: list[MusicGenerationInput] = []
        self.extended: list[MusicGenerationInput] = []
        self._sequence = 0

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        self.generated.append(payload)
        return self._result(payload, "generate")

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        self.extended.append(payload)
        return self._result(payload, "extend")

    def _result(
        self,
        payload: MusicGenerationInput,
        operation: str,
    ) -> MusicGenerationOutput:
        self._sequence += 1
        suffix = f"{operation}-{self._sequence}"
        return MusicGenerationOutput(
            external_task_id=f"suno-task-{suffix}",
            provider_status="complete",
            tracks=[
                MusicTrackOutput(
                    external_id=f"suno-track-{suffix}",
                    title=payload.title,
                    audio_url=f"https://audio.test.invalid/{suffix}.mp3",
                    duration_seconds=95,
                    provider_page_url=f"https://platform.suno.com/test/{suffix}",
                )
            ],
            call=ProviderCallMetadata(
                method="POST",
                endpoint=f"https://api.test.invalid/suno/{operation}",
                is_external=True,
                request_id=f"request-{suffix}",
                usage_unit="songs",
                usage_quantity=1,
            ),
        )
