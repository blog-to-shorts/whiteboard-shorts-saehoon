"""STEP 08. 최종 영상 합성 (Remotion) → jobs/<id>/final.mp4 (1080×1920).

scenes.json 을 Remotion props 로 바꿔 넘기고, 작업 디렉토리를 --public-dir 로 지정해 장면 파일을 그대로 쓴다.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from ..checks import SCENE_PAD_SEC
from ..config import REMOTION_DIR
from ..utils.ffmpeg import probe_video

ACCENT = "#F08C00"


def build_props(doc) -> dict:
    return {
        "title": doc.title, "hook": doc.hook, "sourceUrl": doc.source_url, "fps": doc.fps,
        "padSec": SCENE_PAD_SEC, "accent": ACCENT,
        "scenes": [{
            "id": s.id, "caption": s.caption, "video": s.video, "image": s.image, "audio": s.audio,
            "duration": s.duration or 0, "cues": [c.model_dump() for c in s.cues],
        } for s in doc.scenes],
    }


def run(job) -> None:
    doc = job.doc()
    missing = [s.id for s in doc.scenes if not (s.video and s.audio and s.duration)]
    if missing:
        raise RuntimeError(f"장면 {missing}: 영상·음성이 준비되지 않았습니다 (STEP 05~07 먼저)")
    if not (REMOTION_DIR / "node_modules").is_dir():
        raise RuntimeError("remotion/node_modules 가 없습니다. remotion 폴더에서 npm install 을 먼저 실행하세요.")
    props = job.path("render_props.json")
    props.write_text(json.dumps(build_props(doc), ensure_ascii=False), encoding="utf-8")
    out = job.dir / "final.mp4"
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise RuntimeError("npx 를 찾을 수 없습니다 (Node.js 설치 필요)")
    cmd = [npx, "remotion", "render", "src/index.ts", "WhiteboardVideo", str(out),
           f"--props={props}", f"--public-dir={job.dir}", "--log=warn"]
    r = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("Remotion 렌더 실패: " + (r.stderr or r.stdout)[-1500:])
    info = probe_video(out)
    doc.meta["final"] = {"path": "final.mp4", "duration": round(info["duration"], 2),
                         "width": info.get("width"), "height": info.get("height")}
    job.save_doc(doc)
    job.log.info("STEP08: final.mp4 %.1f초 %sx%s", info["duration"], info.get("width"), info.get("height"))
