import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, useVideoConfig } from "remotion";
import type { SceneProps } from "../types";
import { Subtitle } from "./Subtitle";

// 그림 영역: 2:3 화이트보드 그림(1024x1536)을 9:16 화면 가운데에 배치
const BOX = { top: 300, width: 900, height: 1350 };

export const SceneClip: React.FC<{ scene: SceneProps; accent: string }> = ({ scene, accent }) => {
  const { fps, width } = useVideoConfig();
  // 드로잉 영상은 음성 길이만큼만 재생하고, 그 뒤(장면 여백)는 같은 위치의 완성 그림이 이어서 보인다.
  const videoFrames = Math.max(1, Math.floor(scene.duration * fps) - 1);
  const box: React.CSSProperties = {
    position: "absolute",
    top: BOX.top,
    left: (width - BOX.width) / 2,
    width: BOX.width,
    height: BOX.height,
    objectFit: "contain",
  };
  return (
    <AbsoluteFill style={{ backgroundColor: "#fff" }}>
      <div
        style={{
          position: "absolute",
          top: 120,
          left: 60,
          right: 60,
          textAlign: "center",
          fontFamily: '"Pretendard", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif',
          fontWeight: 900,
          fontSize: 82,
          color: "#111",
          wordBreak: "keep-all",
        }}
      >
        <span style={{ boxShadow: `inset 0 -26px 0 ${accent}55` }}>{scene.caption}</span>
      </div>
      {scene.image ? <Img src={staticFile(scene.image)} style={box} /> : null}
      {scene.video ? (
        <Sequence durationInFrames={videoFrames} layout="none">
          <OffthreadVideo src={staticFile(scene.video)} muted style={box} />
        </Sequence>
      ) : null}
      {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
      <Subtitle cues={scene.cues} />
    </AbsoluteFill>
  );
};
