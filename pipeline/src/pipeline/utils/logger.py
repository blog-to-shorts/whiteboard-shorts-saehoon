"""작업별 로그: 콘솔 + jobs/<id>/pipeline.log."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def get_logger(job_dir: Path | None = None, name: str = "wbs") -> logging.Logger:
    logger = logging.getLogger(f"{name}.{job_dir.name}" if job_dir else name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if job_dir:
        job_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(job_dir / "pipeline.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    logger.propagate = False
    return logger
