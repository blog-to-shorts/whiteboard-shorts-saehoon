"""파이프라인 데이터 구조. scenes.json 이 단계 사이의 유일한 계약이다.

장면 수는 코드에 고정하지 않는다. scenes 배열 길이가 곧 영상의 장면 수다.
경로는 모두 작업 디렉토리(jobs/<id>/) 기준 상대경로로 저장한다.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field


class Source(BaseModel):
    """STEP 01 결과: 블로그 원문."""

    url: str = ""
    title: str
    text: str
    images: list[str] = Field(default_factory=list)
    site: str = ""
    extractor: str = ""


class Analysis(BaseModel):
    """STEP 02 결과: 원문 핵심 분석."""

    core_message: str
    key_points: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)  # 숫자·고유명사 등 대본에서 바뀌면 안 되는 사실
    audience: str = ""
    tone: str = ""
    visual_motif: str = ""  # 장면마다 반복할 시각 요소(그림체 일관성용)


class Word(BaseModel):
    text: str
    start: float  # 장면 오디오 기준 초
    end: float


class Cue(BaseModel):
    text: str
    start: float
    end: float


class Scene(BaseModel):
    id: int
    narration: str  # TTS로 읽는 문장(구어체)
    caption: str = ""  # 화면 상단 핵심 키워드
    image_prompt: str = ""  # 장면 그림 설명(영문)
    source: list[str] = Field(default_factory=list)  # 근거가 된 원문 문장
    image: str | None = None  # assets/images/scene_01.png
    audio: str | None = None  # assets/audio/scene_01.mp3
    video: str | None = None  # videos/scene_01.mp4
    subtitle: str | None = None  # assets/subtitles/scene_01.srt
    duration: float | None = None  # 실제 음성 길이(초)
    words: list[Word] = Field(default_factory=list)
    cues: list[Cue] = Field(default_factory=list)


class ScenesDoc(BaseModel):
    title: str
    hook: str = ""
    source_url: str = ""
    aspect_ratio: str = "9:16"
    fps: int = 30
    target_duration: int = 45
    style_preset: str = ""
    style_prompt: str = ""
    visual_motif: str = ""
    scenes: list[Scene]
    meta: dict = Field(default_factory=dict)


def save_json(path: Path, model: BaseModel | dict) -> None:
    """원자적 저장: 임시 파일에 쓴 뒤 교체. 병렬 단계가 쓰다 만 파일을 읽지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = model.model_dump(mode="json") if isinstance(model, BaseModel) else model
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for i in range(5):  # Windows: 다른 프로세스(백엔드 조회 등)가 잠깐 열고 있으면 교체가 실패할 수 있음
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1 * (i + 1))
    os.replace(tmp, path)


def load_json(path: Path, model: type[BaseModel]):
    return model.model_validate_json(path.read_text(encoding="utf-8"))
