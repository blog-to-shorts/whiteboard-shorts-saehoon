# AI 화이트보드 숏폼 자동 생성 파이프라인

블로그 URL 또는 원문을 넣으면 AI 가 핵심을 분석하고, 장면별 대본과 흑백 화이트보드 일러스트를 만든 뒤,
**드로잉 애니메이션 · 한국어 내레이션 · 자막이 들어간 30~60초 세로형(1080×1920) MP4** 를 자동으로 만든다.

- 아키텍처 기준: [MVP 구성안](https://github.com/blog-to-shorts/ai-whiteboard-shorts-project-proposal) — React + FastAPI + Python AI Pipeline(STEP 01~08) + whiteboard-animator + Remotion
- 이전 프로젝트 `blog-to-shorts`(Node)에서 검증한 부분을 옮겨 왔다: EXAONE 대본 작성·자동 검사·1회 수정, Edge 음성, Remotion 합성, 네이버 본문 추출 규칙

## 시연 영상 (자동 생성 결과)

서로 다른 주제 3건 — 블로그 URL 하나로 만든 초안, 사람 수정 없음 (EXAONE 대본 · OpenAI `gpt-image-2` 그림 · whiteboard-animator 드로잉 · ElevenLabs 음성 · Remotion 합성)

| 과학 · 광합성 | 요리 · 김치찌개 | 건강 · 러닝 무릎 통증 |
|---|---|---|
| [sci-photo.mp4](docs/demo/sci-photo.mp4) · 31.7초 | [cook-kimchi.mp4](docs/demo/cook-kimchi.mp4) · 42.7초 | [health-knee.mp4](docs/demo/health-knee.mp4) · 41.6초 |

세 편 모두 30~60초 · 자막 싱크 오차 0.0초 · 편당 STEP 04~08 약 1분 35초. 그림체 개선 전·후: [전](docs/demo/style_before_econ-rate.png) / [후](docs/demo/style_after_econ-rate.png)

## 시연 웹페이지

```bash
uv sync --extra animator && (cd remotion && npm install) && (cd frontend && npm install && npm run build)
uv run uvicorn app.main:app --app-dir backend --port 8000
```

http://localhost:8000 — URL 입력 → STEP 01~08 진행 상황 → 영상 미리보기·다운로드 → 장면별 대본 수정 후 부분 재생성 → 품질 지표 · 개선 전·후 평가표. 자세한 화면 구성은 [frontend/README.md](frontend/README.md).
API 키(`EXAONE_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`·`ELEVENLABS_VOICE_ID`)는 서버를 켜는 터미널의 환경변수나 `.env` 에 있어야 한다.

## 가이드라인 단계별 산출물

| 단계 | 항목 | 구현 위치 | 실행 | 상태 |
|---|---|---|---|---|
| **1. 설계** | 블로그→대본→이미지→영상 처리 과정 | [docs/01_pipeline_design.md §1](docs/01_pipeline_design.md) | — | 완료 |
| | 대본 품질·그림체 일관성 평가 기준 | [docs/01_pipeline_design.md §3](docs/01_pipeline_design.md) | — | 완료 |
| | 평가용 샘플 콘텐츠 선정 | [eval/samples.json](eval/samples.json) (15건·13개 분야) | `wbs-eval fetch` | 완료 (15/15 추출 성공) |
| **2. 대본·프롬프트** | 본문 핵심 분석·요약 | `steps/s02_analyze.py`, `prompts/analyze_v1.md` | `wbs run --to 2` | 완료 |
| | 30~60초 대본 생성 · 장면 분할 | `steps/s03_script.py`, `prompts/script_v2.md`, `checks.py` | `wbs run --to 3` | 완료 |
| | 장면별 이미지 프롬프트 | `script_v2.md` [image_prompt 규칙] + `s04_image.compose_prompt` | — | 완료 |
| **3. 일러스트** | 장면별 화이트보드 라인 이미지 | `steps/s04_image.py`, `images/` (OpenAI `gpt-image-2`) | `wbs run --from 4` | 완료 (실제 생성 35장) |
| | 스타일 프리셋 | `prompts/styles.json` (`marker_mono`, `marker_accent`, 기준선 `marker_mono_v1`) | `--style` | 완료 |
| | 장면 간 그림체 일관성 확인 · 초기 품질 측정 | `eval/style.py` (+ CRAFT 글자 영역) | `wbs-eval style --job <id>` | 완료 (test-cafe 6/6 통과) |
| **4. TTS·자막·영상** | TTS | `steps/s05_tts.py`, `tts/` (Edge·ElevenLabs) | `--tts edge|elevenlabs` | 완료 (Edge·ElevenLabs 둘 다 영상까지 검증) |
| | 자막 SRT | `steps/s07_subtitle.py`, `subtitles.py` (단어 타이밍 기반) | — | 완료 (싱크 오차 0.0초) |
| | 이미지·음성·자막 결합 9:16 출력 | `steps/s06_animate.py`(whiteboard-animator), `steps/s08_render.py`, `remotion/` | `wbs run` | 완료 (39.9초 1080×1920) |
| **5. 평가·개선** | 샘플 10~20건 품질 평가 | `eval/cli.py`, `eval/metrics.py`, `eval/judge.py` | `wbs-eval script` | 1차 완료 21/30건 · 9건은 EXAONE 일일 한도로 `--resume` 대기 |
| | 대본 정확성·길이·구조 | 자동 검사 + LLM 심사 | `wbs-eval script` | [보고서](docs/05_evaluation_report.md) §2 |
| | 그림체 일관성 | 이미지 지표 + CRAFT 글자 영역 | `wbs-eval images` | [보고서](docs/05_evaluation_report.md) §3 (3건·30장) |
| | 프롬프트 개선 전·후 비교 | 대본 `script_v1`→`v2`, 그림 `marker_mono_v1`→`marker_mono` | `wbs-eval script` · `wbs-eval images` | 1차 비교 완료 · v3 계획 수립 |

## 구조

```
whiteboard-shorts/
├── backend/app/            FastAPI: main.py, models.py, routers/jobs.py, services/job_runner.py
├── pipeline/src/pipeline/
│   ├── run.py              오케스트레이터 (STEP 01~08, 04·05 병렬, 부분 재실행)
│   ├── config.py · schema.py(scenes.json) · context.py(작업 디렉토리·상태·측정) · checks.py(대본 검사)
│   ├── steps/              s01_extract … s08_render
│   ├── llm/                EXAONE·OpenAI (OpenAI 호환, 토큰·비용 집계, 초당 호출 제한)
│   ├── images/             OpenAI Image · placeholder · 흑백 후처리
│   ├── tts/                Edge · ElevenLabs (단어 타이밍)
│   ├── prompts/            analyze_v1 · script_v1(개선 전) · script_v2(개선 후) · styles.json
│   ├── eval/               평가 CLI · 대본 지표 · LLM 심사 · 그림체 지표
│   └── utils/              ffmpeg · logger · retry · jsonx
├── remotion/src/           Root.tsx · WhiteboardVideo.tsx · components/SceneClip.tsx · Subtitle.tsx · types.ts
├── frontend/src/           시연 웹 UI (React + TypeScript + Vite): App · NewJob · JobList · JobDetail · SceneEditor · EvalPanel
├── vendor/                 whiteboard-animator 체크아웃 위치(선택, 기본은 PyPI 설치)
├── eval/                   samples.json(목록) · samples/(원문, git 제외) · runs/(평가 결과)
├── jobs/<id>/              source·analysis·scenes·metrics·status.json, assets/, videos/, subtitles.srt, final.mp4
└── docs/                   01_pipeline_design.md · 05_evaluation_report.md · eval_*_report.md · eval_summary.json · demo/
```

## 설치

필요: Python 3.11+ & [uv](https://docs.astral.sh/uv/), Node.js 20+, FFmpeg(ffmpeg·ffprobe 가 PATH 에)

```bash
uv sync                          # Python 워크스페이스 (pipeline + backend)
cd remotion && npm install       # Remotion
cp .env.example .env             # 키 입력 (또는 사용자 환경변수)
```

### 드로잉 엔진 설치 (whiteboard-animator, MIT)
설치하지 않으면 STEP 06 이 단순 스윕 공개 방식으로 대체되어 영상은 나오지만, 구성안의 "손으로 그리는" 효과는 이 엔진이 필요하다.

```bash
uv sync --extra animator         # PyPI whiteboard-animator (CRAFT 텍스트 검출 모델 약 83MB 포함)
```

## 실행

```bash
# 전체: URL → final.mp4
uv run wbs run --url https://blog.naver.com/<id>/<logNo>

# 원문 직접 입력 (추출 실패 대비)
uv run wbs run --text-file post.txt --title "제목"

# 키 없이 흐름 확인 (이미지 대신 자리표시 그림)
uv run wbs run --url ... --image placeholder

# 부분 재실행: 장면 2 이미지만 다시 → 이후 단계
uv run wbs run --job <id> --from 4 --scenes 2
```

API 서버

```bash
uv run uvicorn app.main:app --app-dir backend --port 8000     # 문서: http://localhost:8000/docs
```

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/jobs` | `{url | text, title, options{llm, image, tts, animator, style, prompt_version, scene_count, target_duration}}` → 작업 ID |
| GET | `/api/jobs` · `/api/jobs/{id}` | 진행 상태(state, step, error, video_url) |
| GET | `/api/jobs/{id}/scenes` · `/metrics` · `/log` · `/subtitles.srt` · `/video` | 대본·측정값·로그·자막·MP4 |
| POST | `/api/jobs/{id}/rerun` | `{from_step, scenes, edits[{id, narration, caption, image_prompt}]}` 수정 후 부분 재생성 |
| GET | `/api/jobs/{id}/quality` · `/files/{path}` | 품질 지표(5단계와 같은 계산) · 장면 이미지·음성 |
| GET | `/api/eval/summary` | 최신 개선 전·후 평가 요약 |

## 평가

```bash
uv run wbs-eval fetch                              # 샘플 원문 수집
uv run wbs-eval script --versions v1,v2            # 개선 전·후 대본 평가 → eval/runs/<ts>/report.md
uv run wbs-eval style --job <id>                   # 그림체 일관성
uv run wbs-eval jobs --job <id> --job <id2>        # 길이·자막 싱크·생성 시간·비용
```

## 알려진 한계·주의

- **대본 AI 기본값은 OpenAI `gpt-4.1-mini`** (대본 1편 약 15초·$0.006). EXAONE 은 `LLM_PROVIDER=exaone` 또는 `--llm exaone` —
  `reasoning_effort=low` 에서도 추론 토큰이 많아 대본 1편에 수 분이 걸리고 하루 100회 호출 제한이 있다.
- **EXAONE 호출 한도**: 초당 1회. LLM 어댑터가 프로세스 안에서 호출 간격을 1.2초로 맞춘다.
- **EXAONE 비용**: 공개 단가가 없어 비용은 '미확인'으로 기록된다(토큰 수는 기록).
- **이미지 속 글자**: 이미지 모델은 한글을 정확히 그리지 못해 스타일 프리셋에서 글자를 금지하고, 글자는 Remotion 자막·키워드로 넣는다.
- **ElevenLabs 무료 플랜**: Voice Library(공유) 목소리는 API 로 쓸 수 없고(402), 기본(premade) 목소리만 된다. 동시 요청 2개 제한에 맞춰 TTS 를 2개씩 만든다.
