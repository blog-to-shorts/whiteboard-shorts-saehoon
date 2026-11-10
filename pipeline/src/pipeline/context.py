"""작업(Job) 컨텍스트: 작업 디렉토리, 설정, 로그, 단계 간 파일 읽기/쓰기, 상태·측정값 기록."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from .config import Settings
from .schema import Analysis, ScenesDoc, Source, load_json, save_json
from .utils.logger import get_logger

STEP_NAMES = {
    1: "블로그 본문 추출",
    2: "AI 콘텐츠 분석",
    3: "대본 및 장면 생성",
    4: "화이트보드 이미지 생성",
    5: "한국어 TTS 생성",
    6: "드로잉 애니메이션 생성",
    7: "자막 생성 및 영상 전처리",
    8: "최종 영상 합성",
}


class Job:
    def __init__(self, settings: Settings, job_id: str | None = None, only_scenes: set[int] | None = None):
        self.settings = settings
        self.id = job_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.dir = settings.jobs_dir / self.id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = get_logger(self.dir)
        self.only_scenes = only_scenes
        self._llm = None
        self._lock = threading.RLock()
        self._metrics = self._read("metrics.json") or {"steps": {}, "cost": {}}

    # ── 경로 ──
    def path(self, rel: str) -> Path:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def rel(self, p: Path) -> str:
        return p.relative_to(self.dir).as_posix()

    def wants(self, scene_id: int) -> bool:
        return self.only_scenes is None or scene_id in self.only_scenes

    # ── 단계 산출물 ──
    def source(self) -> Source:
        return load_json(self.dir / "source.json", Source)

    def analysis(self) -> Analysis:
        return load_json(self.dir / "analysis.json", Analysis)

    def doc(self) -> ScenesDoc:
        with self._lock:
            return load_json(self.dir / "scenes.json", ScenesDoc)

    def save_doc(self, doc: ScenesDoc) -> None:
        with self._lock:
            save_json(self.dir / "scenes.json", doc)

    def merge_scenes(self, updates: dict[int, dict], meta: dict | None = None) -> None:
        """병렬 단계(STEP 04·05)가 서로의 필드를 덮어쓰지 않도록, 잠금 상태에서 다시 읽고 자기 필드만 반영한다."""
        with self._lock:
            doc = self.doc()
            for s in doc.scenes:
                for k, v in updates.get(s.id, {}).items():
                    setattr(s, k, v)
            if meta:
                doc.meta.update(meta)
            save_json(self.dir / "scenes.json", doc)

    @property
    def llm(self):
        if self._llm is None:
            from .llm import LLM

            self._llm = LLM(self.settings.llm_provider)
        return self._llm

    # ── 상태·측정 ──
    def _read(self, name: str):
        p = self.dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def status(self, **kw) -> None:
        with self._lock:
            try:
                cur = self._read("status.json") or {"id": self.id}
            except json.JSONDecodeError:  # 이전 비정상 종료로 깨진 상태 파일은 새로 쓴다
                cur = {"id": self.id}
            cur.update(kw, updated_at=time.time())
            save_json(self.dir / "status.json", cur)

    def record_step(self, step: int, seconds: float, ok: bool, error: str = "") -> None:
        with self._lock:
            self._metrics["steps"][str(step)] = {
                "name": STEP_NAMES[step], "seconds": round(seconds, 1), "ok": ok, **({"error": error} if error else {}),
            }
            self.save_metrics()

    def add_cost(self, key: str, value: dict) -> None:
        with self._lock:
            self._metrics["cost"][key] = value
            self.save_metrics()

    def save_metrics(self) -> None:
        with self._lock:
            self._metrics["settings"] = self.settings.public()
            save_json(self.dir / "metrics.json", self._metrics)

    @property
    def metrics(self) -> dict:
        return self._metrics
