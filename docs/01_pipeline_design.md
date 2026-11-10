# 1단계. AI 생성 파이프라인 및 평가 기준 설계

> 기반: [AI 화이트보드 숏폼 자동 생성 파이프라인 MVP 구성안](https://github.com/blog-to-shorts/ai-whiteboard-shorts-project-proposal) — React + FastAPI + Python AI Pipeline + whiteboard-animator + Remotion
> 이 문서는 가이드라인 1단계(처리 과정 설계 · 평가 기준 정의 · 평가용 샘플 선정)의 산출물이다.

## 1. 처리 과정: 블로그 → 대본 → 이미지 → 영상

```
입력: 블로그 URL 또는 원문 텍스트
  │
  ▼ STEP 01 본문 추출         Requests + BeautifulSoup        → source.json
  │   네이버: PostView 주소로 바꿔 iframe 본문 직접 수집 / 그 외: 글자 수 최대 블록
  │   실패 시 원문 직접 입력(--text-file, API text)
  ▼ STEP 02 콘텐츠 분석       LLM (EXAONE | OpenAI)            → analysis.json
  │   핵심 메시지 · 핵심 내용(순서) · 바뀌면 안 되는 사실 · 반복 시각 요소(visual_motif)
  ▼ STEP 03 대본·장면 생성    LLM + 자동 검사 1회 수정          → scenes.json
  │   장면별 narration · caption · image_prompt · source(근거 원문)
  │
  ├──────────────┬─────────────────────── (STEP 04·05 병렬)
  ▼ STEP 04 이미지          ▼ STEP 05 TTS
  │ OpenAI Image + 스타일    │ Edge | ElevenLabs
  │ 프리셋 + 흑백 후처리      │ 단어별 타이밍 + 실제 길이 측정
  │ → assets/images/*.png    │ → assets/audio/*.mp3
  └──────────────┬──────────────┘
  ▼ STEP 06 드로잉 애니메이션 whiteboard-animator (음성 길이에 맞춰 그림)  → videos/raw/*.mp4
  ▼ STEP 07 자막·전처리       단어 타이밍 → 자막 큐 → SRT, FFmpeg H.264   → assets/subtitles/*.srt, subtitles.srt, videos/*.mp4
  ▼ STEP 08 최종 합성         Remotion (scenes.json → props, 장면 수·길이 자동) → final.mp4 (1080×1920)
```

### 단계 간 계약: `scenes.json`
- 장면 수를 코드에 고정하지 않는다. `scenes` 배열 길이가 곧 영상의 장면 수다.
- 경로는 작업 디렉토리(`jobs/<id>/`) 기준 상대경로로 저장한다. Remotion 은 이 디렉토리를 `--public-dir` 로 그대로 쓴다.
- `duration` 은 STEP 05 가 실제 음성 길이를 재서 채운다. 이후 단계(드로잉 길이, 자막 시간, 영상 길이)는 모두 이 값을 따른다.

### 수정·재생성
- `wbs run --job <id> --from N [--scenes 2,3]` 또는 `POST /api/jobs/{id}/rerun` (edits 로 narration·caption·image_prompt 수정)
- STEP 04~07 은 지정한 장면만 다시 만들고, STEP 08 은 항상 전체를 다시 합성한다.

### 측정 기록 (모든 작업)
- `metrics.json`: 단계별 소요 시간·성공 여부·오류, LLM 토큰(추론 토큰 포함), 이미지 장수, TTS 글자 수, 비용 추정
- `status.json`: 진행 상태(백엔드 API 가 읽음), `pipeline.log`: 단계별 로그

## 2. 기술 구성과 어댑터

| 구분 | 기본값 | 대체 | 전환 |
|---|---|---|---|
| 대본·분석 LLM | EXAONE (`k-exaone_v2.5`) | OpenAI (`gpt-4.1-mini`) | `LLM_PROVIDER` |
| 이미지 | OpenAI Image (`gpt-image-1`, 1024×1536) | placeholder (개발용) | `IMAGE_PROVIDER` |
| TTS | Edge 신경망 음성 (무료) | ElevenLabs | `TTS_PROVIDER` |
| 드로잉 | whiteboard-animator | 단순 스윕 공개(대체 방식) | `ANIMATOR` |

구성안은 대본·이미지 모두 OpenAI, TTS 는 ElevenLabs 를 명시한다. 현재 환경에 있는 키(EXAONE)로 바로 돌 수 있게 기본값을 정하고, 키를 넣으면 구성안 그대로 동작하도록 어댑터로 분리했다. 모델 비교 자체도 5단계 평가 대상이 된다.

## 3. 평가 기준

### 3.1 대본 품질 (정확성·길이·구조)

| 축 | 지표 | 측정 방법 | 통과 기준 |
|---|---|---|---|
| 길이 | 예상 길이(초) | 내레이션 글자 수 ÷ 6.1자/초 + 장면 여백 0.4초 | 30~60초 |
| 길이 | 실제 영상 길이 | ffprobe(final.mp4) | 30~60초 |
| 형식 | 형식 위반 수 | 자동 검사(checks.py): hook ≤18자, caption ≤16자, narration 25~75자, 합계 170~330자, 장면 4~8개, 이모지·기호 금지 | 0건 |
| 구조 | 구조 통과 | 필수 필드(hook·caption·narration·image_prompt) 존재, 장면 수 범위 | 통과 |
| 구조 | 구조 점수 | LLM 심사: 도입(문제 제시)→전개(원문 순서)→결론(추천 대상) | ≥4 / 5 |
| 정확성 | 근거 확인 장면 비율 | 장면 `source` 와 원문의 최장 공통 구간 비율 ≥0.6 | ≥90% |
| 정확성 | 정확성 점수 | LLM 심사: 숫자·이름·순서·인과가 원문과 일치, 지어낸 정보 없음 | ≥4 / 5 |
| 정확성 | 왜곡 지적 수 | LLM 심사의 distortions 개수 | 0건 |
| 포괄성 | 핵심 포함 점수 | LLM 심사: 원문 핵심 누락 여부 | ≥4 / 5 |
| 자연스러움 | 자연스러움 점수 | LLM 심사: 구어체·TTS 적합성 | ≥4 / 5 |
| 장면 적합성 | 그림 설명력 점수 | LLM 심사: image_prompt 가 그 장면 내레이션 핵심을 그림으로 설명하는가 | ≥4 / 5 |

LLM 심사는 개선 전·후에 같은 프롬프트(`pipeline/eval/judge.py`)와 같은 모델을 쓴다. 생성 모델과 심사 모델이 같으면 자기 평가 편향이 생길 수 있어 보고서에 심사 모델을 함께 적고, OpenAI 키가 있으면 `--judge openai` 로 교차 심사한다.

### 3.2 이미지 스타일 일관성 (그림체)

드로잉 엔진 입력 조건(흰 바탕 위 잉크, 평면 마커 그림)과 장면 간 일관성을 이미지 지표로 잰다(`pipeline/eval/style.py`).

| 지표 | 의미 | 기준 |
|---|---|---|
| white_bg | 흰 배경 비율 | 모든 장면 ≥ 0.55 |
| gray_tones | 잉크 중 회색(음영·그라데이션) 비율 | 모든 장면 ≤ 0.25 |
| colorfulness | 채도 지표(Hasler–Süsstrunk) | 흑백 프리셋: 모든 장면 ≤ 8 |
| stroke_px CV | 선 굵기의 장면 간 변동계수 | ≤ 0.35 |
| ink CV | 잉크 양의 장면 간 변동계수 | ≤ 0.6 |
| detail CV | 묘사 복잡도(가장자리 밀도) 변동계수 | ≤ 0.6 |

일관성 점수 = 통과한 항목 수 / 전체 항목 수. 사람 검수용 보조 항목(작업별 체크): 반복 시각 요소가 같은 모습으로 나오는가, 그림에 글자가 섞이지 않았는가.

### 3.3 영상·자동화

| 항목 | 측정 | 기준 |
|---|---|---|
| 자동화 성공 | URL 입력 → final.mp4 까지 수동 개입 없이 완료 | 성공 |
| 음성·자막 싱크 | 자막 큐 시작과 실제 단어 발화 시작의 최대 차이 | ≤ 0.1초 |
| 자막 범위 | SRT 마지막 시간 ≤ 영상 길이 | 통과 |
| 드로잉 품질 | (사람 검수) 그림이 이해하기 쉬운 순서로 나타나는가, 음성보다 늦지 않은가 | 장면별 O/X |
| 생성 시간 | metrics.json 총 소요·단계별 소요 | 기록 |
| 비용 | LLM 토큰·이미지 장수·TTS 글자 수 × 단가 | 기록(단가 미공개 모델은 '미확인') |
| 수정 용이성 | 장면 1개 수정 후 부분 재실행 성공·소요 시간 | 성공 |

구성안의 강조점대로 **AI 이미지 품질(대본을 정확히 시각화했는가)** 과 **드로잉 품질(자연스러운 순서로 그려지는가)** 은 따로 기록한다.

## 4. 평가용 샘플 콘텐츠

선정 기준
1. 화이트보드 설명 영상에 맞는 **정보형 글**(개념·과정·방법·비교·체크리스트) 위주 + 대조군으로 개인 후기 1건
2. **분야를 넓게**: 경제·재테크·세금·건강·IT·과학·육아·요리·법률·반려동물·자기계발·여행·후기 (13개 분야)
3. **숫자 밀도가 다른 글**을 섞어 정확성(숫자·고유명사 보존)을 시험: 금리·공제 항목·계산식이 많은 글 포함
4. **글 길이 분산**: 1,580자 ~ 6,350자 (30~60초 압축 난이도 차이)
5. 최근 글, 공개 글, 네이버 블로그(가장 흔한 입력)

목록: [`eval/samples.json`](../eval/samples.json) (15건). 원문은 저작권 때문에 저장소에 넣지 않고 `wbs-eval fetch` 로 받아 쓴다.

| ID | 분야 | 특성 |
|---|---|---|
| econ-rate | 경제 | 개념 설명 + 숫자 |
| econ-fomc | 경제 | 용어 해설·인과 |
| fin-isa | 재테크 | 장단점 비교 |
| tax-yearend | 세금 | 항목 나열·숫자 많음 |
| health-knee | 건강 | 원인→대처 흐름 |
| it-python | IT·교육 | 단계별 로드맵 |
| sci-photo | 과학 | 과정·도식 설명 |
| parent-sleep | 육아 | 방법·팁 (가장 긴 글) |
| cook-kimchi | 요리 | 순서가 있는 레시피 |
| law-jeonse | 법률·생활 | 체크리스트 |
| law-jeonse2 | 법률·생활 | 체크리스트 + 계산식 |
| pet-sep | 반려동물 | 훈련 단계 |
| self-pomo | 자기계발 | 방법 소개 |
| travel-jeju | 여행 | 일정·장소 나열 |
| review-cafe | 방문 후기 | 개인 경험·의견 (대조군) |
