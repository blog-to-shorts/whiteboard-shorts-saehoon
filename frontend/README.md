# frontend — 시연용 웹 UI (React + TypeScript + Vite)

구성안의 React 프론트엔드. 한 화면에서 다음을 시연한다.

| 영역 | 내용 | 쓰는 API |
|---|---|---|
| 새 영상 만들기 | 블로그 URL 또는 원문, 옵션(대본 AI·목소리·그림·프롬프트 버전·장면 수·목표 길이) | `POST /api/jobs` |
| 진행 상황 | STEP 01~08 실시간 표시(04·05 병렬), 단계별 소요 시간, 로그 | `GET /api/jobs/{id}`, `/log` |
| 결과 | 9:16 영상 미리보기·MP4 다운로드, 품질 지표(길이·자막 싱크·그림체·드로잉·시간·비용) | `/video`, `/quality` |
| 대본·장면 | 장면별 그림·키워드·내레이션·그림 설명·원문 근거·음성 → 고치면 필요한 단계만 다시 | `/scenes`, `/files/…`, `POST /rerun` |
| 품질 평가 | 프롬프트·스타일 개선 전·후 비교표 | `GET /api/eval/summary` |

수정 후 다시 만들 때 고친 항목에 따라 시작 단계를 고른다: 그림 설명 → STEP 04(그 장면만), 내레이션 → STEP 05(그 장면만), 키워드만 → STEP 08(합성만).

## 실행

```bash
npm install
npm run build          # dist/ 생성 → FastAPI 가 http://localhost:8000/ 에서 제공
```

개발 모드(핫 리로드): 백엔드를 8000 에 켜 둔 채 `npm run dev` → http://localhost:5173 (`/api` 는 8000 으로 프록시)
