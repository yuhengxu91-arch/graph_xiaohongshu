import { Composition, registerRoot } from "remotion";
import { KnowledgeVideo, type KnowledgeVideoProps } from "./compositions/KnowledgeVideo";
import { DataVizVideo, type DataVizVideoProps } from "./compositions/DataVizVideo";
import { TEMPLATES } from "./templates";

/**
 * Remotion 入口 — 自动注册所有模板
 *
 * 模板在 templates.ts 中定义配置，
 * 新增模板只需添加 Composition 和配置即可。
 */
const RemotionRoot: React.FC = () => {
  const knowledgeTemplate = TEMPLATES.find((t) => t.id === "KnowledgeVideo")!;
  const dataVizTemplate = TEMPLATES.find((t) => t.id === "DataVizVideo")!;

  return (
    <>
      {/* ═══ 模板 1: 干货技能卡 ═══ */}
      <Composition<any, KnowledgeVideoProps>
        id={knowledgeTemplate.id}
        component={KnowledgeVideo}
        durationInFrames={knowledgeTemplate.defaultDurationFrames}
        fps={knowledgeTemplate.fps}
        width={knowledgeTemplate.width}
        height={knowledgeTemplate.height}
        defaultProps={{
          title: "示例视频标题",
          scenes: [
            {
              narration: "这是一段示例旁白文本。",
              audioUrl: "",
              audioDuration: 5,
              imageUrl: "",
              sceneTitle: "示例标题",
              keyPoints: ["要点一", "要点二", "要点三", "要点四"],
              codeExample: "4 个要点 · 干货满满",
              sceneType: "content",
            },
          ],
        }}
        calculateMetadata={({ props }) => {
          const titleDuration = 3;
          const outroDuration = 3;
          const contentDuration = (props.scenes as KnowledgeVideoProps["scenes"]).reduce(
            (sum: number, s: { audioDuration?: number }) => sum + (s.audioDuration || 5),
            0
          );
          const totalSeconds = titleDuration + contentDuration + outroDuration;
          return {
            durationInFrames: Math.ceil(totalSeconds * knowledgeTemplate.fps),
          };
        }}
      />

      {/* ═══ 模板 2: 数据可视化 ═══ */}
      <Composition<any, DataVizVideoProps>
        id={dataVizTemplate.id}
        component={DataVizVideo}
        durationInFrames={dataVizTemplate.defaultDurationFrames}
        fps={dataVizTemplate.fps}
        width={dataVizTemplate.width}
        height={dataVizTemplate.height}
        defaultProps={{
          title: "数据洞察示例",
          scenes: [
            {
              sceneType: "number_flip",
              sceneTitle: "核心指标",
              narration: "让我们看看这些数据。",
              audioUrl: "",
              audioDuration: 8,
              metrics: [
                { label: "用户增长", value: 1200, suffix: "万", color: "#818cf8" },
                { label: "转化率", value: 85, suffix: "%", color: "#34d399" },
              ],
            },
          ],
        }}
        calculateMetadata={({ props }) => {
          const introDuration = 3;
          const outroDuration = 3;
          const contentDuration = (props.scenes as DataVizVideoProps["scenes"]).reduce(
            (sum: number, s: { audioDuration?: number }) => sum + (s.audioDuration || 8),
            0
          );
          const totalSeconds = introDuration + contentDuration + outroDuration;
          return {
            durationInFrames: Math.ceil(totalSeconds * dataVizTemplate.fps),
          };
        }}
      />

      {/* 后续新模板在这里注册 */}
    </>
  );
};

registerRoot(RemotionRoot);
