import React from "react";
import { AbsoluteFill, interpolate, Series, useCurrentFrame, useVideoConfig } from "remotion";
import { SceneClip } from "./components/SceneClip";
import { sceneFrames, type VideoProps } from "./types";

// 장면 수·길이는 scenes.json(props)에서 정해진다. 코드에 고정하지 않는다.
export const WhiteboardVideo: React.FC<VideoProps> = (props) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const hookOpacity = interpolate(frame, [0, 6, fps * 2.4, fps * 2.8], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "#fff" }}>
      <Series>
        {props.scenes.map((s) => (
          <Series.Sequence key={s.id} durationInFrames={sceneFrames(s, fps, props.padSec)}>
            <SceneClip scene={s} accent={props.accent} />
          </Series.Sequence>
        ))}
      </Series>
      {props.hook ? (
        <div
          style={{
            position: "absolute",
            top: 40,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: hookOpacity,
          }}
        >
          <span
            style={{
              fontFamily: '"Pretendard", "Malgun Gothic", sans-serif',
              fontWeight: 900,
              fontSize: 44,
              color: "#fff",
              background: "#111",
              borderRadius: 999,
              padding: "8px 30px",
            }}
          >
            {props.hook}
          </span>
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          bottom: 50,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: '"Malgun Gothic", sans-serif',
          fontSize: 26,
          color: "#888",
        }}
      >
        원문: {props.title.slice(0, 40)}
      </div>
    </AbsoluteFill>
  );
};
