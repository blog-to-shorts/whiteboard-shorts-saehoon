"""파이프라인 실행 서비스. 작업은 백그라운드 스레드에서 돌고, 상태는 jobs/<id>/status.json 이 기준이다.

동시에 여러 작업을 돌리면 이미지·LLM API 한도와 CPU(드로잉)를 같이 쓰므로 한 번에 MAX_WORKERS 개만 실행한다.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.config import Settings
from pipeline.context import Job
from pipeline.run import run_pipeline
from pipeline.schema import save_json

from ..models import CreateJob, JobOptions, RerunJob

MAX_WORKERS = 1
_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="wbs-job")


def settings_from(opts: JobOptions | None) -> Settings:
    s = Settings()
    if opts:
        for attr, val in [("llm_provider", opts.llm), ("image_provider", opts.image), ("tts_provider", opts.tts),
                          ("animator", opts.animator), ("style_preset", opts.style),
                          ("prompt_version", opts.prompt_version)]:
            if val:
                setattr(s, attr, val)
        s.scene_count, s.target_duration = opts.scene_count, opts.target_duration
    return s


def jobs_dir() -> Path:
    return Settings().jobs_dir


def read_status(job_id: str) -> dict | None:
    p = jobs_dir() / job_id / "status.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _safe(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except Exception:  # noqa: BLE001 — 실패는 status.json·pipeline.log 에 이미 기록됨
        pass


def submit(req: CreateJob) -> str:
    s = settings_from(req.options)
    job = Job(s)  # 작업 디렉토리·ID 를 먼저 만들어 바로 돌려준다
    job.status(state="queued", input={"url": req.url, "has_text": bool(req.text), "title": req.title},
               options=s.public())
    _pool.submit(_safe, run_pipeline, s, url=req.url, text=req.text, title=req.title, job_id=job.id)
    return job.id


def rerun(job_id: str, req: RerunJob) -> None:
    s = settings_from(req.options)
    if req.options is None:  # 기존 작업 설정 유지
        prev = (read_status(job_id) or {}).get("options") or {}
        for k, v in prev.items():
            if hasattr(s, k) and v is not None:
                setattr(s, k, v)
    job = Job(s, job_id)
    if req.edits:
        doc = job.doc()
        by_id = {e.id: e for e in req.edits}
        for sc in doc.scenes:
            e = by_id.get(sc.id)
            if not e:
                continue
            for field in ("narration", "caption", "image_prompt"):
                v = getattr(e, field)
                if v is not None:
                    setattr(sc, field, v)
        job.save_doc(doc)
        save_json(job.dir / "edits.json", [e.model_dump() for e in req.edits])
    job.status(state="queued", step=req.from_step)
    only = set(req.scenes) if req.scenes else None
    _pool.submit(_safe, run_pipeline, s, job_id=job_id, start=req.from_step, end=8, only_scenes=only)
