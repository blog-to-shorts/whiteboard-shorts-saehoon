import React from "react";
import { Composition } from "remotion";
import { WhiteboardVideo } from "./WhiteboardVideo";
import { sceneFrames, type VideoProps } from "./types";

const defaultProps: VideoProps = {
  title: "미리보기",
  hook: "화이트보드 숏폼",
  sourceUrl: "",
  fps: 30,
  padSec: 0.4,
  accent: "#F08C00",
  scenes: [
    { id: 1, caption: "장면 1", video: null, image: null, audio: null, duration: 3, cues: [{ text: "자막 예시", start: 0, end: 3 }] },
  ],
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="WhiteboardVideo"
    component={WhiteboardVideo}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={90}
    defaultProps={defaultProps}
    calculateMetadata={({ props }) => ({
      fps: props.fps,
      durationInFrames: props.scenes.reduce((a, s) => a + sceneFrames(s, props.fps, props.padSec), 0),
    })}
  />
);
