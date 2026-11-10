"""요청/응답 모델."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class JobOptions(BaseModel):
    llm: Literal["exaone", "openai"] | None = None
    image: Literal["openai", "placeholder"] | None = None
    tts: Literal["edge", "elevenlabs"] | None = None
    animator: Literal["whiteboard", "simple"] | None = None
    style: str | None = None
    prompt_version: Literal["v1", "v2"] | None = None
    scene_count: int = Field(5, ge=4, le=8)
    target_duration: int = Field(45, ge=30, le=60)


class CreateJob(BaseModel):
    url: str | None = None
    text: str | None = None
    title: str | None = None
    options: JobOptions = Field(default_factory=JobOptions)

    @model_validator(mode="after")
    def need_input(self):
        if not (self.url or self.text):
            raise ValueError("url 또는 text 중 하나가 필요합니다")
        return self


class SceneEdit(BaseModel):
    id: int
    narration: str | None = None
    caption: str | None = None
    image_prompt: str | None = None


class RerunJob(BaseModel):
    """수정 용이성: 대본·장면을 고친 뒤 필요한 단계만 다시 실행."""

    from_step: int = Field(4, ge=1, le=8)
    scenes: list[int] | None = None  # STEP 04~07 을 이 장면만
    edits: list[SceneEdit] = Field(default_factory=list)
    options: JobOptions | None = None


class JobStatus(BaseModel):
    id: str
    state: str = "queued"
    step: int | None = None
    step_name: str | None = None
    error: str | None = None
    total_seconds: float | None = None
    video_url: str | None = None
    updated_at: float | None = None
    title: str | None = None
    thumbnail_url: str | None = None
    video_seconds: float | None = None
    steps_done: dict[str, dict] = Field(default_factory=dict)  # metrics.json 의 단계별 소요·성공
