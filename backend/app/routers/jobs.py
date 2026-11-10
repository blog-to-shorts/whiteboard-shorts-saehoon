"""작업 생성/조회 API."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..models import CreateJob, JobStatus, RerunJob
from ..security import check_daily_quota
from ..services import job_runner

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_ID = re.compile(r"^[\w.-]{1,80}$")


def _dir(job_id: str):
    if not _ID.match(job_id):
        raise HTTPException(400, "잘못된 작업 ID")
    d = job_runner.jobs_dir() / job_id
    if not d.is_dir():
        raise HTTPException(404, "작업 없음")
    return d


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (json.JSONDecodeError, OSError):  # 파이프라인이 쓰는 중이면 다음 조회에서 읽는다
        return {}


def _status(job_id: str) -> JobStatus:
    d = _dir(job_id)
    st = job_runner.read_status(job_id) or {"id": job_id}
    scenes = _read(d / "scenes.json")
    src = _read(d / "source.json") if not scenes else {}
    video = (d / "final.mp4").is_file() and st.get("state") in ("done", "partial")
    thumb = next((s.get("image") for s in scenes.get("scenes", []) if s.get("image")), None)
    return JobStatus(
        id=job_id, state=st.get("state", "queued"), step=st.get("step"), step_name=st.get("step_name"),
        error=st.get("error"), total_seconds=st.get("total_seconds"), updated_at=st.get("updated_at"),
        video_url=f"/api/jobs/{job_id}/video?v={int(st.get('updated_at') or 0)}" if video else None,
        title=scenes.get("title") or src.get("title") or (st.get("input") or {}).get("title"),
        thumbnail_url=f"/api/jobs/{job_id}/files/{thumb}" if thumb else None,
        video_seconds=(scenes.get("meta", {}).get("final") or {}).get("duration"),
        steps_done=_read(d / "metrics.json").get("steps", {}),
    )


@router.post("", response_model=JobStatus, status_code=202)
def create_job(req: CreateJob):
    check_daily_quota()
    return _status(job_runner.submit(req))


@router.get("", response_model=list[JobStatus])
def list_jobs(limit: int = 20):
    root = job_runner.jobs_dir()
    dirs = sorted((d for d in root.iterdir() if (d / "status.json").is_file()),
                  key=lambda d: (d / "status.json").stat().st_mtime, reverse=True) if root.is_dir() else []
    return [_status(d.name) for d in dirs[:limit]]


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    _dir(job_id)
    return _status(job_id)


@router.get("/{job_id}/scenes")
def get_scenes(job_id: str):
    p = _dir(job_id) / "scenes.json"
    if not p.is_file():
        raise HTTPException(404, "아직 대본이 없습니다 (STEP 03 전)")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/{job_id}/metrics")
def get_metrics(job_id: str):
    p = _dir(job_id) / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


@router.get("/{job_id}/subtitles.srt", response_class=PlainTextResponse)
def get_srt(job_id: str):
    p = _dir(job_id) / "subtitles.srt"
    if not p.is_file():
        raise HTTPException(404, "자막 없음 (STEP 07 전)")
    return p.read_text(encoding="utf-8")


@router.get("/{job_id}/video")
def get_video(job_id: str):
    p = _dir(job_id) / "final.mp4"
    if not p.is_file():
        raise HTTPException(404, "영상 없음")
    return FileResponse(p, media_type="video/mp4", filename=f"{job_id}.mp4")


@router.get("/{job_id}/files/{rel:path}")
def get_file(job_id: str, rel: str):
    """작업 산출물(장면 이미지·음성·장면 영상) 제공. 작업 디렉토리 밖은 막는다."""
    d = _dir(job_id).resolve()
    p = (d / rel).resolve()
    if d not in p.parents or not p.is_file() or p.suffix.lower() not in {".png", ".jpg", ".mp3", ".mp4", ".srt"}:
        raise HTTPException(404, "파일 없음")
    return FileResponse(p)


@router.get("/{job_id}/quality")
def get_quality(job_id: str):
    """완성 작업 품질 지표(5단계 평가와 같은 계산): 길이·자막 싱크·생성 시간·비용 + 그림체 일관성."""
    from pipeline.eval.metrics import job_metrics
    from pipeline.eval.style import style_report

    d = _dir(job_id)
    if not (d / "scenes.json").is_file() or not (d / "metrics.json").is_file():
        raise HTTPException(404, "아직 측정할 결과가 없습니다")
    out = job_metrics(d)
    imgs = sorted((d / "assets" / "images").glob("scene_*.png"))
    if imgs:
        rep = style_report(imgs, mono="accent" not in (_read(d / "scenes.json").get("style_preset") or ""))
        out["style"] = {"score": rep["consistency_score"], "checks": rep["checks"], "cv": rep["cv"]}
    return out


@router.get("/{job_id}/log", response_class=PlainTextResponse)
def get_log(job_id: str, tail: int = 80):
    p = _dir(job_id) / "pipeline.log"
    return "\n".join(p.read_text(encoding="utf-8").splitlines()[-tail:]) if p.is_file() else ""


@router.post("/{job_id}/rerun", response_model=JobStatus, status_code=202)
def rerun_job(job_id: str, req: RerunJob):
    _dir(job_id)
    if (job_runner.read_status(job_id) or {}).get("state") in ("running", "queued"):
        raise HTTPException(409, "이미 실행 중인 작업입니다")
    if req.from_step < 8:  # 합성만 다시 하는 경우(STEP 08)는 API 비용이 없어 한도에서 뺀다
        check_daily_quota()
    job_runner.rerun(job_id, req)
    return _status(job_id)
