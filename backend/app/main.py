"""FastAPI 앱 엔트리포인트.

실행: uv run uvicorn app.main:app --app-dir backend --port 8000
- 시연 화면: http://localhost:8000/        (frontend/dist 를 빌드해 두면 여기서 바로 제공)
- API 문서:  http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipeline.config import PROJECT_ROOT, key_status

from .routers import evaluation, jobs
from .security import BasicAuthMiddleware, quota_status

app = FastAPI(title="AI 화이트보드 숏폼 파이프라인", version="0.1.0")
app.add_middleware(BasicAuthMiddleware)  # DEMO_PASSWORD 가 있을 때만 동작
app.add_middleware(  # React 개발 서버(vite)용
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(jobs.router)
app.include_router(evaluation.router)


@app.get("/api/health")
def health():
    return {"ok": True, "keys": key_status(), "quota": quota_status()}  # 키는 설정 여부만, 값은 내보내지 않음


_dist = PROJECT_ROOT / "frontend" / "dist"
if _dist.is_dir():  # API 라우트를 먼저 등록하고 마지막에 정적 파일을 붙인다
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
