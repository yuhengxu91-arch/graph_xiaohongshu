import { AbsoluteFill, Sequence, Audio, useVideoConfig } from "remotion";
import { TitleScene } from "./TitleScene";
import { ContentScene } from "./ContentScene";
import { OutroScene } from "./OutroScene";

/**
 * 单个场景数据
 */
export interface SceneData {
  narration: string;
  audioUrl: string;
  audioDuration: number; // 秒
  imageUrl: string;
  sceneTitle: string;         // 场景标题文字
  keyPoints: string[];        // 要点列表
  codeExample: string;        // 代码示例
  sceneType: string;          // intro / content / outro
}

/**
 * KnowledgeVideo 输入属性
 */
export type KnowledgeVideoProps = {
  title: string;
  scenes: SceneData[];
};

const TITLE_DURATION = 3; // 开场 3 秒
const OUTRO_DURATION = 3; // 结尾 3 秒

/**
 * 知识讲解型视频主 Composition
 * 结构: 开场标题 → 内容段落(N段，带音频) → 结尾CTA
 */
export const KnowledgeVideo: React.FC<KnowledgeVideoProps> = ({ title, scenes }) => {
  const { fps } = useVideoConfig();

  // 计算每个段落的起始帧
  let currentFrame = Math.ceil(TITLE_DURATION * fps);
  const sceneTimings = scenes.map((scene) => {
    const startFrame = currentFrame;
    const durationFrames = Math.ceil((scene.audioDuration || 5) * fps);
    currentFrame += durationFrames;
    return { startFrame, durationFrames };
  });

  const outroStartFrame = currentFrame;
  const outroDurationFrames = Math.ceil(OUTRO_DURATION * fps);

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%)",
        fontFamily: "'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
      }}
    >
      {/* 开场标题 */}
      <Sequence from={0} durationInFrames={Math.ceil(TITLE_DURATION * fps)}>
        <TitleScene title={title} />
      </Sequence>

      {/* 内容段落 + 音频 */}
      {scenes.map((scene, index) => {
        const timing = sceneTimings[index];
        return (
          <Sequence
            key={index}
            from={timing.startFrame}
            durationInFrames={timing.durationFrames}
          >
            {/* 视觉内容 */}
            <ContentScene
              narration={scene.narration}
              imageUrl={scene.imageUrl}
              sceneIndex={index}
              totalScenes={scenes.length}
              sceneTitle={scene.sceneTitle || ""}
              keyPoints={scene.keyPoints || []}
              codeExample={scene.codeExample || ""}
            />
            {/* TTS 音频 */}
            {scene.audioUrl && (
              <Audio src={scene.audioUrl} volume={1} />
            )}
          </Sequence>
        );
      })}

      {/* 结尾 CTA */}
      <Sequence from={outroStartFrame} durationInFrames={outroDurationFrames}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  );
};
