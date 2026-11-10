import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { Cue } from "../types";

// 장면 오디오 기준 시간의 자막 큐 중 지금 말하는 것 하나를 보여준다(SRT 와 같은 시간축).
export const Subtitle: React.FC<{ cues: Cue[] }> = ({ cues }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cue = cues.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 60,
        right: 60,
        bottom: 150,
        display: "flex",
        justifyContent: "center",
      }}
    >
      <span
        style={{
          fontFamily: '"Pretendard", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif',
          fontWeight: 800,
          fontSize: 62,
          lineHeight: 1.25,
          color: "#111",
          background: "rgba(255,255,255,0.92)",
          border: "5px solid #111",
          borderRadius: 18,
          padding: "10px 26px",
          textAlign: "center",
          wordBreak: "keep-all",
        }}
      >
        {cue.text}
      </span>
    </div>
  );
};
