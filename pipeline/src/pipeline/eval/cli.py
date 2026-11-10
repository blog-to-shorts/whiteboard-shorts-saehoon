"""평가 CLI (wbs-eval).

  wbs-eval fetch                         eval/samples.json 의 URL 원문을 eval/samples/<id>.json 으로 수집
  wbs-eval script --versions v1,v2       샘플 전체에 대해 대본 생성(개선 전·후) + 자동 지표 + LLM 심사 → 보고서
  wbs-eval style --job <id> [--job ...]  작업별 장면 이미지 그림체 일관성
  wbs-eval jobs --job <id> [--job ...]   완성 작업 지표(길이·싱크·생성 시간·비용) + 그림체
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from ..config import PROJECT_ROOT, Settings
from ..schema import Analysis, Source, save_json

EVAL_DIR = PROJECT_ROOT / "eval"
SAMPLES_DIR = EVAL_DIR / "samples"
RUNS_DIR = EVAL_DIR / "runs"


def _manifest() -> list[dict]:
    return json.loads((EVAL_DIR / "samples.json").read_text(encoding="utf-8"))["samples"]


def cmd_fetch(a) -> int:
    from ..steps.s01_extract import extract

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for s in _manifest():
        out = SAMPLES_DIR / f"{s['id']}.json"
        if out.is_file() and not a.force:
            ok += 1
            continue
        try:
            src = extract(s["url"])
            save_json(out, src)
            ok += 1
            print(f"OK   {s['id']:<14} {len(src.text):>5}자  {src.title[:40]}")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {s['id']:<14} {e}")
        time.sleep(1.0)  # 소량·저속 조회
    print(f"{ok}/{len(_manifest())} 샘플 준비됨 → {SAMPLES_DIR}")
    return 0


def _load_samples(ids: str | None) -> list[tuple[dict, Source]]:
    want = set(ids.split(",")) if ids else None
    out = []
    for s in _manifest():
        if want and s["id"] not in want:
            continue
        p = SAMPLES_DIR / f"{s['id']}.json"
        if p.is_file():
            out.append((s, Source.model_validate_json(p.read_text(encoding="utf-8"))))
    return out


def _script_one(sample: dict, src: Source, version: str, llm_provider: str, judge_provider: str,
                cache: Path, scene_count: int) -> dict:
    from ..llm import LLM
    from ..steps.s02_analyze import analyze
    from ..steps.s03_script import generate
    from .judge import judge_script
    from .metrics import script_metrics

    llm = LLM(llm_provider)
    t = time.time()
    analysis = None
    if version != "v1":  # v1 = 개선 전 기준선: 분석·자동 수정 없이 단일 프롬프트
        ap = cache / f"{sample['id']}.analysis.json"
        if ap.is_file():
            analysis = Analysis.model_validate_json(ap.read_text(encoding="utf-8"))
        else:
            analysis = analyze(llm, src.title, src.text)
            save_json(ap, analysis)
    out = generate(llm, version=version, title=src.title, text=src.text, analysis=analysis,
                   scene_count=scene_count, target_duration=45, fix=version != "v1")
    gen_sec = round(time.time() - t, 1)
    m = script_metrics(out["hook"], out["scenes"], src.text)
    judge_llm = LLM(judge_provider)
    j = judge_script(judge_llm, src.title, src.text, out["hook"], out["scenes"])
    return {"sample": sample["id"], "category": sample.get("category", ""), "version": version,
            "llm": llm.label, "judge": judge_llm.label, "gen_seconds": gen_sec, "llm_usage": llm.summary(),
            "hook": out["hook"], "scenes": out["scenes"], "fixed": out["fixed"],
            "first_problem_count": len(out["first_problems"]), "metrics": m, "judge_scores": j}


def cmd_script(a) -> int:
    samples = _load_samples(a.samples)
    if not samples:
        print("샘플 원문이 없습니다. 먼저 wbs-eval fetch", file=sys.stderr)
        return 1
    versions = a.versions.split(",")
    run_dir = Path(a.resume) if a.resume else RUNS_DIR / (datetime.now().strftime("%Y%m%d-%H%M") + "-script")
    run_dir.mkdir(parents=True, exist_ok=True)
    res_path = run_dir / "results.jsonl"
    done = set()
    if res_path.is_file():
        for line in res_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["sample"], r["version"]))
    llm_p = a.llm or Settings().llm_provider
    judge_p = a.judge or llm_p
    tasks = [(s, src, v) for s, src in samples for v in versions if (s["id"], v) not in done]
    print(f"평가 {len(tasks)}건 (샘플 {len(samples)} × 버전 {versions}), 생성 {llm_p}, 심사 {judge_p} → {run_dir}")

    def work(t):
        s, src, v = t
        try:
            r = _script_one(s, src, v, llm_p, judge_p, run_dir, a.scene_count)
        except Exception as e:  # noqa: BLE001
            r = {"sample": s["id"], "category": s.get("category", ""), "version": v, "error": str(e)[:300]}
        with res_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        sc = r.get("judge_scores", {}).get("mean")
        print(f"  {s['id']:<14} {v}  {'ERROR ' + r['error'][:60] if 'error' in r else f'심사 {sc} / {r['gen_seconds']}s'}")
        return r

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, tasks))
    report = write_script_report(run_dir)
    print(f"보고서: {report}")
    return 0


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.mean(vals), 3) if vals else None


def write_script_report(run_dir: Path) -> Path:
    rows = [json.loads(x) for x in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    ok = [r for r in rows if "error" not in r]
    versions = sorted({r["version"] for r in rows})
    # 비교는 모든 버전이 성공한 샘플끼리만(짝지은 비교). 한쪽만 성공한 샘플은 평균에서 뺀다.
    paired = {s for s in {r["sample"] for r in ok}
              if all(any(r["sample"] == s and r["version"] == v for r in ok) for v in versions)}
    ok_all = ok
    ok = [r for r in ok if r["sample"] in paired]
    agg = {}
    for v in versions:
        rs = [r for r in ok if r["version"] == v]
        agg[v] = {
            "n": len(rs),
            "errors": len([r for r in rows if r["version"] == v and "error" in r]),
            "length_ok": _mean([1.0 if r["metrics"]["length_ok"] else 0.0 for r in rs]),
            "structure_ok": _mean([1.0 if r["metrics"]["structure_ok"] else 0.0 for r in rs]),
            "format_violations": _mean([r["metrics"]["format_violations"] for r in rs]),
            "grounded_rate": _mean([r["metrics"]["grounded_rate"] for r in rs]),
            "est_seconds": _mean([r["metrics"]["est_seconds"] for r in rs]),
            **{k: _mean([r["judge_scores"][k] for r in rs])
               for k in ["accuracy", "coverage", "structure", "naturalness", "visual_fit", "mean"]},
            "distortions": _mean([len(r["judge_scores"]["distortions"]) for r in rs]),
            "gen_seconds": _mean([r["gen_seconds"] for r in rs]),
        }
    save_json(run_dir / "summary.json", agg)
    label = {"length_ok": "길이 30~60초 통과율", "structure_ok": "구조 통과율", "format_violations": "형식 위반(건/편)",
             "grounded_rate": "근거 확인 장면 비율", "est_seconds": "예상 길이(초)", "accuracy": "정확성(1~5)",
             "coverage": "핵심 포함(1~5)", "structure": "구조(1~5)", "naturalness": "자연스러움(1~5)",
             "visual_fit": "그림 설명력(1~5)", "mean": "심사 평균(1~5)", "distortions": "왜곡 지적(건/편)",
             "gen_seconds": "생성 시간(초/편)"}
    errors = [r for r in rows if "error" in r]
    lines = [f"# 대본 품질 평가 — 개선 전·후 비교", "",
             f"- 실행: `{run_dir.name}` · 샘플 {len({r['sample'] for r in rows})}건 · 버전 {', '.join(versions)}",
             f"- **비교 표는 모든 버전이 성공한 샘플 {len(paired)}건만 사용**(짝지은 비교). "
             f"오류 {len(errors)}건은 제외: " + (", ".join(sorted({f"{r['sample']}/{r['version']}" for r in errors})) or "없음"),
             f"- 생성 모델: {ok[0]['llm'] if ok else '-'} · 심사 모델: {ok[0]['judge'] if ok else '-'}"
             " (같은 모델이 심사하면 자기 평가 편향 가능)", "",
             "| 지표 | " + " | ".join(versions) + (" | 변화 |" if len(versions) == 2 else " |"),
             "|---|" + "---|" * len(versions) + ("---|" if len(versions) == 2 else "")]
    for k, name in label.items():
        vals = [agg[v][k] for v in versions]
        row = f"| {name} | " + " | ".join("-" if x is None else f"{x:g}" for x in vals) + " |"
        if len(versions) == 2 and None not in vals:
            row += f" {vals[1] - vals[0]:+.3g} |"
        lines.append(row)
    lines += ["", "## 샘플별", "", "| 샘플 | 분야 | " + " | ".join(f"{v} 심사/길이/근거" for v in versions) + " |",
              "|---|---|" + "---|" * len(versions)]
    for sid in sorted({r["sample"] for r in rows}):
        cells, cat = [], ""
        for v in versions:
            r = next((x for x in ok_all if x["sample"] == sid and x["version"] == v), None)
            if not r:
                cells.append("오류" if any(x["sample"] == sid and x["version"] == v for x in rows) else "-")
                continue
            cat = r["category"]
            m = r["metrics"]
            cells.append(f"{r['judge_scores']['mean']} / {m['est_seconds']}s{'' if m['length_ok'] else '✗'} / "
                         f"{m['grounded_rate']:.0%}")
        lines.append(f"| {sid} | {cat} | " + " | ".join(cells) + " |")
    lines += ["", "## 심사 코멘트·왜곡 지적 (버전별 최대 5건)", ""]
    for v in versions:
        lines.append(f"### {v}")
        for r in [x for x in ok if x["version"] == v][:5]:
            d = "; ".join(r["judge_scores"]["distortions"][:2]) or "없음"
            lines.append(f"- **{r['sample']}**: {r['judge_scores']['comment']} (왜곡: {d})")
        lines.append("")
    path = run_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _results(run_dir: Path) -> list[dict]:
    return [json.loads(x) for x in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]


def seed_job(run_dir: Path, sample_id: str, version: str, job_id: str, style: str):
    """평가에서 만든 대본으로 작업 디렉토리를 만든다(STEP 01~03 결과를 그대로 재사용 → 같은 대본으로 비교)."""
    from ..context import Job
    from ..schema import Scene, ScenesDoc
    from ..steps.s04_image import load_style

    r = next((x for x in _results(run_dir) if x["sample"] == sample_id and x["version"] == version and "error" not in x), None)
    if r is None:
        raise ValueError(f"{run_dir.name} 에 {sample_id}/{version} 결과가 없습니다")
    s = Settings()
    s.style_preset = style
    job = Job(s, job_id)
    src = Source.model_validate_json((SAMPLES_DIR / f"{sample_id}.json").read_text(encoding="utf-8"))
    save_json(job.dir / "source.json", src)
    ap = run_dir / f"{sample_id}.analysis.json"
    motif = ""
    if ap.is_file():
        a = Analysis.model_validate_json(ap.read_text(encoding="utf-8"))
        save_json(job.dir / "analysis.json", a)
        motif = a.visual_motif
    doc = ScenesDoc(title=src.title, hook=r["hook"], source_url=src.url, style_preset=style,
                    style_prompt=load_style(style)["prompt"], visual_motif=motif,
                    scenes=[Scene(id=i, **{k: sc.get(k) for k in ("caption", "narration", "image_prompt", "source")})
                            for i, sc in enumerate(r["scenes"], 1)],
                    meta={"prompt_version": version, "llm": r["llm"], "seeded_from": f"{run_dir.name}/{sample_id}"})
    job.save_doc(doc)
    job.status(state="seeded", options=s.public())
    return job, s


def cmd_images(a) -> int:
    """그림체 개선 전·후: 같은 대본에 스타일 프리셋만 바꿔 이미지를 만들고 일관성 지표를 비교한다."""
    from ..run import run_pipeline
    from .style import style_report

    run_dir = Path(a.run)
    styles = a.styles.split(",")
    samples = a.samples.split(",")
    out_dir = run_dir / "images"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for sid in samples:
        for st in styles:
            jid = f"img-{sid}-{st}"
            job_dir = Settings().jobs_dir / jid
            if not (job_dir / "assets" / "images").is_dir() or a.force:
                _, s = seed_job(run_dir, sid, a.version, jid, st)
                try:
                    run_pipeline(s, job_id=jid, start=4, end=4)
                except Exception as e:  # noqa: BLE001
                    rows.append({"sample": sid, "style": st, "error": str(e)[:200]})
                    print(f"  {sid:<14} {st:<16} ERROR {e}")
                    continue
            imgs = sorted((job_dir / "assets" / "images").glob("scene_*.png"))
            rep = style_report(imgs, mono="accent" not in st)
            rows.append({"sample": sid, "style": st, "job": jid, **rep})
            print(f"  {sid:<14} {st:<16} 일관성 {rep['consistency_score']:.0%}  CV(선굵기) {rep['cv']['stroke_px']}")
            _contact_sheet(imgs, out_dir / f"{sid}__{st}.png")
    save_json(out_dir / "image_results.json", rows)
    path = _image_report(run_dir, rows, styles)
    print(f"보고서: {path}")
    return 0


def _contact_sheet(imgs: list[Path], out: Path) -> None:
    from PIL import Image

    tiles = [Image.open(p).convert("RGB").resize((256, 384)) for p in imgs]
    sheet = Image.new("RGB", (256 * len(tiles) + 8 * (len(tiles) - 1), 384), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 264, 0))
    sheet.save(out)


def _image_report(run_dir: Path, rows: list[dict], styles: list[str]) -> Path:
    ok = [r for r in rows if "error" not in r]
    check_names = sorted({k for r in ok for k in r["checks"]})
    lines = ["# 그림체 일관성 평가 — 스타일 프리셋 개선 전·후", "",
             "같은 대본(같은 image_prompt)에 스타일 프리셋만 바꿔 생성한 장면 이미지를 비교한다.", "",
             "| 지표 | " + " | ".join(styles) + " |", "|---|" + "---|" * len(styles)]

    def col(st, fn):
        rs = [r for r in ok if r["style"] == st]
        return fn(rs) if rs else None

    metrics = {
        "일관성 점수(평균)": lambda rs: _mean([r["consistency_score"] for r in rs]),
        "선 굵기 CV(평균)": lambda rs: _mean([r["cv"]["stroke_px"] for r in rs]),
        "잉크 양 CV(평균)": lambda rs: _mean([r["cv"]["ink"] for r in rs]),
        "복잡도 CV(평균)": lambda rs: _mean([r["cv"]["detail"] for r in rs]),
        "회색·음영 비율(평균)": lambda rs: _mean([v["gray_tones"] for r in rs for v in r["images"].values()]),
        "채도(평균)": lambda rs: _mean([v["colorfulness"] for r in rs for v in r["images"].values()]),
        "흰 배경 비율(평균)": lambda rs: _mean([v["white_bg"] for r in rs for v in r["images"].values()]),
        "글자 영역 비율(평균, CRAFT 참고)": lambda rs: _mean([r.get("text_area_mean") for r in rs]),
    }
    for name, fn in metrics.items():
        lines.append(f"| {name} | " + " | ".join("-" if (x := col(st, fn)) is None else f"{x:g}" for st in styles) + " |")
    for c in check_names:
        lines.append(f"| 통과율: {c} | " + " | ".join(
            "-" if (x := col(st, lambda rs, c=c: _mean([1.0 if r['checks'].get(c) else 0.0 for r in rs]))) is None
            else f"{x:.0%}" for st in styles) + " |")
    lines += ["", "## 샘플별 일관성 점수", "", "| 샘플 | " + " | ".join(styles) + " |", "|---|" + "---|" * len(styles)]
    for sid in sorted({r["sample"] for r in rows}):
        cells = []
        for st in styles:
            r = next((x for x in rows if x["sample"] == sid and x["style"] == st), None)
            cells.append("오류" if (r is None or "error" in r) else f"{r['consistency_score']:.0%}")
        lines.append(f"| {sid} | " + " | ".join(cells) + " |")
    lines += ["", "장면 이미지 모음: `images/<샘플>__<스타일>.png`"]
    p = run_dir / "image_report.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def cmd_make_jobs(a) -> int:
    """평가 대본으로 영상 작업을 만들고(선택) STEP 04~08 까지 실행한다."""
    from ..run import run_pipeline

    run_dir = Path(a.run)
    for sid in a.samples.split(","):
        jid = f"video-{sid}"
        _, s = seed_job(run_dir, sid, a.version, jid, a.style)
        print(f"작업 생성: {jid}")
        if a.render:
            try:
                run_pipeline(s, job_id=jid, start=4, end=8)
                print(f"  완료: jobs/{jid}/final.mp4")
            except Exception as e:  # noqa: BLE001
                print(f"  실패: {e}")
    return 0


def cmd_style(a) -> int:
    from .style import style_report

    jobs_dir = Settings().jobs_dir
    out = {}
    for jid in a.job:
        d = jobs_dir / jid
        imgs = sorted((d / "assets" / "images").glob("scene_*.png"))
        doc = json.loads((d / "scenes.json").read_text(encoding="utf-8"))
        mono = "accent" not in (doc.get("style_preset") or "")
        out[jid] = {"style_preset": doc.get("style_preset"), "image_model": doc.get("meta", {}).get("image_model"),
                    **style_report(imgs, mono=mono)}
        print(f"{jid}: 일관성 {out[jid]['consistency_score']:.0%}  " +
              "  ".join(f"{k}={'O' if v else 'X'}" for k, v in out[jid]["checks"].items()))
    if a.out:
        save_json(Path(a.out), out)
    return 0


def cmd_jobs(a) -> int:
    from .metrics import job_metrics
    from .style import style_report

    jobs_dir = Settings().jobs_dir
    rows = {}
    for jid in a.job:
        d = jobs_dir / jid
        m = job_metrics(d)
        imgs = sorted((d / "assets" / "images").glob("scene_*.png"))
        if imgs:
            m["style"] = style_report(imgs)["consistency_score"]
        rows[jid] = m
        print(f"{jid}: 영상 {m['video_seconds']}s ({'O' if m['duration_ok'] else 'X'}) · 생성 {m['generation_seconds']}s · "
              f"비용 {m['cost_usd'] if m['cost_usd'] is not None else '미확인'} · 자막 오차 {m['subtitle_max_drift_sec']}s · "
              f"그림체 {m.get('style', '-')}")
    if a.out:
        save_json(Path(a.out), rows)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wbs-eval", description="AI 생성 품질 평가")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--force", action="store_true")
    s = sub.add_parser("script")
    s.add_argument("--versions", default="v1,v2")
    s.add_argument("--samples", help="샘플 ID 목록 (콤마)")
    s.add_argument("--llm", choices=["exaone", "openai"])
    s.add_argument("--judge", choices=["exaone", "openai"], help="심사 모델 (기본: 생성 모델과 같음)")
    s.add_argument("--scene-count", type=int, default=5)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--resume", help="이어서 할 eval/runs/<dir>")
    st = sub.add_parser("style")
    st.add_argument("--job", action="append", required=True)
    st.add_argument("--out")
    j = sub.add_parser("jobs")
    j.add_argument("--job", action="append", required=True)
    j.add_argument("--out")
    im = sub.add_parser("images", help="스타일 프리셋 개선 전·후 그림체 비교")
    im.add_argument("--run", required=True, help="대본을 가져올 eval/runs/<dir>")
    im.add_argument("--samples", required=True)
    im.add_argument("--styles", default="marker_mono_v1,marker_mono")
    im.add_argument("--version", default="v2")
    im.add_argument("--force", action="store_true")
    mj = sub.add_parser("make-jobs", help="평가 대본으로 영상 작업 생성")
    mj.add_argument("--run", required=True)
    mj.add_argument("--samples", required=True)
    mj.add_argument("--version", default="v2")
    mj.add_argument("--style", default="marker_mono")
    mj.add_argument("--render", action="store_true", help="STEP 04~08 까지 실행")
    a = p.parse_args(argv)
    return {"fetch": cmd_fetch, "script": cmd_script, "style": cmd_style, "jobs": cmd_jobs,
            "images": cmd_images, "make-jobs": cmd_make_jobs}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
