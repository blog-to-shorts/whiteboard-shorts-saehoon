import { useEffect, useState } from "react";
import { api, type EvalSummary } from "../api";

const SCRIPT_ROWS: [string, string, "up" | "down" | null, (v: number) => string][] = [
  ["length_ok", "길이 30~60초 통과율", "up", pct],
  ["format_violations", "형식 위반 (건/편)", "down", num],
  ["grounded_rate", "근거 확인 장면 비율", "up", pct],
  ["distortions", "왜곡 지적 (건/편)", "down", num],
  ["accuracy", "정확성 (1~5)", "up", num],
  ["naturalness", "자연스러움 (1~5)", "up", num],
  ["coverage", "핵심 포함 (1~5)", "up", num],
  ["visual_fit", "그림 설명력 (1~5)", "up", num],
  ["est_seconds", "예상 길이 (초)", null, num],
  ["gen_seconds", "생성 시간 (초/편)", "down", num],
];

function pct(v: number) {
  return `${Math.round(v * 100)}%`;
}
function num(v: number) {
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

export function EvalPanel() {
  const [s, setS] = useState<EvalSummary | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.evalSummary().then(setS).catch((e) => setErr(e.message));
  }, []);
  if (err) return <div className="card msg err">{err}</div>;
  if (!s) return <div className="card">불러오는 중…</div>;
  if (!s.script) return <div className="card">아직 평가 결과가 없어요. <code>uv run wbs-eval script</code> 를 실행하세요.</div>;

  const v1 = s.script.v1 ?? {};
  const v2 = s.script.v2 ?? {};
  const styles = groupImages(s.images ?? []);

  return (
    <div className="eval">
      <div className="card">
        <h2>대본 품질 — 프롬프트 개선 전(v1) · 후(v2)</h2>
        <p className="hint">
          같은 샘플 {v2.n ?? "-"}건 짝지은 비교 · 실행 {s.run} · 생성·심사 모델 EXAONE (자기 평가 편향 가능)
          {s.errors?.length ? ` · 일일 호출 한도로 미완료 ${s.errors.length}건` : ""}
        </p>
        <table className="cmp">
          <thead>
            <tr>
              <th>지표</th>
              <th>개선 전</th>
              <th>개선 후</th>
              <th>판정</th>
            </tr>
          </thead>
          <tbody>
            {SCRIPT_ROWS.map(([k, label, better, f]) => {
              const a = v1[k] as number | null | undefined;
              const b = v2[k] as number | null | undefined;
              let verdict = "";
              if (better && a != null && b != null && a !== b) verdict = (better === "up" ? b > a : b < a) ? "개선" : "악화";
              return (
                <tr key={k}>
                  <th>{label}</th>
                  <td>{a == null ? "-" : f(a)}</td>
                  <td>
                    <b>{b == null ? "-" : f(b)}</b>
                  </td>
                  <td className={verdict === "개선" ? "good" : verdict === "악화" ? "bad" : ""}>{verdict}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="note">
          개선 전 대본은 평균 2분 반 길이라 쇼츠로 쓸 수 없어요. 대신 원문을 많이 옮겨 ‘핵심 포함’ 점수가 높게 나왔어요.
          다음 개선(v3)은 핵심 누락과 그림 설명력을 목표로 합니다.
        </p>
      </div>

      {styles.length > 0 && (
        <div className="card">
          <h2>그림체 일관성 — 스타일 프리셋 개선 전 · 후</h2>
          <p className="hint">같은 대본에 스타일만 바꿔 생성 · 샘플 {new Set((s.images ?? []).map((i) => i.sample)).size}건</p>
          <table className="cmp">
            <thead>
              <tr>
                <th>스타일</th>
                <th>일관성 점수</th>
                <th>선 굵기 변동</th>
                <th>그림 속 글자 영역</th>
              </tr>
            </thead>
            <tbody>
              {styles.map((g) => (
                <tr key={g.style}>
                  <th>{g.style === "marker_mono_v1" ? "개선 전 (구성안 한 줄)" : g.style === "marker_mono" ? "개선 후 (marker_mono)" : g.style}</th>
                  <td>{pct(g.score)}</td>
                  <td>{num(g.cv)}</td>
                  <td>{g.text == null ? "-" : pct(g.text)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">개선 전 그림에는 영어 글자와 원문에 없는 달러 금액이 들어갔어요. 개선 후에는 거의 사라졌어요.</p>
        </div>
      )}
    </div>
  );
}

function groupImages(rows: NonNullable<EvalSummary["images"]>) {
  const by: Record<string, typeof rows> = {};
  rows.forEach((r) => (by[r.style] ??= []).push(r));
  const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length);
  return Object.entries(by).map(([style, rs]) => ({
    style,
    score: mean(rs.map((r) => r.score)),
    cv: mean(rs.map((r) => r.cv_stroke)),
    text: rs.every((r) => r.text_area != null) ? mean(rs.map((r) => r.text_area as number)) : null,
  }));
}
