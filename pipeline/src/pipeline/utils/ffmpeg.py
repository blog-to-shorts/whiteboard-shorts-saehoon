"""FFmpeg / ffprobe 래퍼."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def require(tool: str = "ffmpeg") -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"{tool} 를 PATH 에서 찾을 수 없습니다. FFmpeg 를 설치하고 터미널을 다시 여세요.")
    return path


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [require("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def probe_video(path: Path) -> dict:
    out = subprocess.run(
        [require("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    s = (data.get("streams") or [{}])[0]
    return {**s, "duration": float(data.get("format", {}).get("duration", 0))}


def to_h264(src: Path, dst: Path, fps: int = 30) -> Path:
    """Remotion 호환용 H.264 / yuv420p / 고정 fps, 오디오 제거(음성은 별도 트랙으로 합성)."""
    tmp = dst.with_suffix(".tmp.mp4")
    subprocess.run(
        [require(), "-y", "-v", "error", "-i", str(src), "-an", "-r", str(fps),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(tmp)],
        check=True,
    )
    tmp.replace(dst)
    return dst
