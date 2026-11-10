"""STEP 06. 드로잉 애니메이션 생성 (whiteboard-animator → 장면별 MP4).

이미지와 음성이 모두 준비된 뒤 실행한다. 음성 길이에 맞춰 그림이 그려지고, 끝난 그림은 음성이 끝날 때까지 유지된다.
ANIMATOR=simple 이거나 whiteboard-animator 를 쓸 수 없으면 단순 스윕 공개 방식으로 대체한다(리스크 대응).
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from ..utils.ffmpeg import require


def _whiteboard(image: Path, audio: Path, out: Path) -> None:
    from whiteboard_animator import Scene, render_video

    render_video([Scene(str(image), audio=str(audio))], str(out), quality="high")


def _simple(image: Path, duration: float, out: Path, fps: int = 24, draw_ratio: float = 0.7) -> None:
    """대체 방식: 잉크 픽셀을 위→아래(약간 사선) 순서로 공개하고, 끝난 그림을 유지한다."""
    from PIL import Image

    img = np.asarray(Image.open(image).convert("RGB"))
    h, w = img.shape[:2]
    h -= h % 2
    w -= w % 2
    img = img[:h, :w]
    ink = img.min(axis=-1) < 240
    yy, xx = np.mgrid[0:h, 0:w]
    order = (yy / h) * 0.8 + (xx / w) * 0.2  # 0~1
    frames = max(1, int(duration * fps))
    draw_frames = max(1, int(frames * draw_ratio))
    cmd = [require(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    white = np.full_like(img, 255)
    try:
        for f in range(frames):
            t = min(1.0, (f + 1) / draw_frames)
            mask = ink & (order <= t)
            frame = np.where(mask[..., None], img, white)
            p.stdin.write(frame.astype(np.uint8).tobytes())
    finally:
        p.stdin.close()
        p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg 대체 드로잉 인코딩 실패")


def run(job) -> None:
    doc = job.doc()
    mode = job.settings.animator
    if mode == "whiteboard":
        try:
            import whiteboard_animator  # noqa: F401
        except ImportError:
            job.log.warning("STEP06: whiteboard-animator 미설치 → 단순 스윕 드로잉으로 대체 (README '드로잉 엔진 설치' 참고)")
            mode = "simple"
    targets = [s for s in doc.scenes if job.wants(s.id)]
    for s in targets:
        if not s.image or not s.audio:
            raise RuntimeError(f"장면 {s.id}: 이미지와 음성이 모두 있어야 드로잉을 만들 수 있습니다 (STEP 04·05 먼저)")

    def one(scene):
        raw = job.path(f"videos/raw/scene_{scene.id:02d}.mp4")
        img, aud = job.dir / scene.image, job.dir / scene.audio
        if mode == "whiteboard":
            try:
                _whiteboard(img, aud, raw)
            except Exception as e:  # noqa: BLE001
                job.log.warning("STEP06: 장면 %d whiteboard-animator 실패 → 대체 방식: %s", scene.id, str(e)[:200])
                _simple(img, scene.duration or 6, raw)
        else:
            _simple(img, scene.duration or 6, raw)
        scene.video = job.rel(raw)
        job.log.info("STEP06: 장면 %d 드로잉 영상 (%s)", scene.id, mode)

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, targets))
    doc.meta["animator"] = mode
    job.save_doc(doc)
