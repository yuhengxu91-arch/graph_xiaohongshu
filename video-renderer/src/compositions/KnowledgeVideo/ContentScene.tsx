import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

interface ContentSceneProps {
  narration: string;
  imageUrl: string;
  sceneIndex: number;
  totalScenes: number;
  sceneTitle: string;
  keyPoints: string[];
  codeExample: string;
}

/**
 * 干货内容场景 — 仿抖音知识类视频风格
 * 结构: 星空背景 → SKILL 编号 → 大标题 → 副描述 → 要点网格卡片 → 数据徽标 → 底部字幕
 * 支持 9:16 竖屏 和 16:9 横屏 自适应布局
 */
export const ContentScene: React.FC<ContentSceneProps> = ({
  narration,
  sceneIndex,
  totalScenes,
  sceneTitle,
  keyPoints,
  codeExample,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  // ═══════════ 是否横屏 ═══════════
  const isLandscape = width > height;

  // 响应式尺寸
  const sizes = isLandscape
    ? {
        paddingBottom: 140,
        paddingH: 80,
        skillFont: 18,
        titleFont: 40,
        subFont: 20,
        pointFont: 22,
        badgeFont: 18,
        captionFont: 26,
        captionBottom: 60,
        maxCardWidth: 800,
        cardPadding: 14,
        pointPadding: "12px 16px",
        dotSize: 8,
        gap: 10,
      }
    : {
        paddingBottom: 420,
        paddingH: 60,
        skillFont: 24,
        titleFont: 52,
        subFont: 26,
        pointFont: 28,
        badgeFont: 22,
        captionFont: 32,
        captionBottom: 380,
        maxCardWidth: 900,
        cardPadding: 20,
        pointPadding: "16px 20px",
        dotSize: 10,
        gap: 12,
      };

  // ═══════════ 场景进出 ═══════════
  const enterProgress = spring({ frame, fps, config: { damping: 18, stiffness: 70 } });
  const enterSlide = interpolate(enterProgress, [0, 1], [40, 0]);
  const exitStart = durationInFrames - 12;
  const exitOpacity = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ═══════════ SKILL 编号 ═══════════
  const skillOpacity = interpolate(frame, [5, 15], [0, 1], { extrapolateRight: "clamp" });
  const skillSlide = interpolate(frame, [5, 15], [15, 0], { extrapolateRight: "clamp" });

  // ═══════════ 主标题 ═══════════
  const titleOpacity = interpolate(frame, [12, 22], [0, 1], { extrapolateRight: "clamp" });
  const titleScale = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  // ═══════════ 副标题 ═══════════
  const subOpacity = interpolate(frame, [20, 30], [0, 1], { extrapolateRight: "clamp" });

  // ═══════════ 分割线 ═══════════
  const lineWidth = interpolate(frame, [18, 32], [0, isLandscape ? 400 : 600], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ═══════════ 代码/数据徽标 ═══════════
  const badgeDelay = 25 + keyPoints.length * 8;
  const badgeOpacity = interpolate(frame, [badgeDelay, badgeDelay + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const badgeScale = spring({
    frame: Math.max(0, frame - badgeDelay),
    fps,
    config: { damping: 12, stiffness: 120 },
  });

  // ═══════════ 底部旁白字幕 ═══════════
  const narrationStart = badgeDelay + 5;
  const narrationOpacity = interpolate(frame, [narrationStart, narrationStart + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ═══════════ 星空粒子 ═══════════
  const stars = Array.from({ length: 30 }, (_, i) => ({
    x: ((i * 137 + 43) % width),
    y: ((i * 89 + 17) % height),
    size: 1 + (i % 3),
    twinkle: 0.2 + Math.sin(frame * 0.03 + i * 1.7) * 0.3,
  }));

  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* ═══ 星空深色背景 ═══ */}
      <AbsoluteFill
        style={{
          background: "linear-gradient(180deg, #080618 0%, #0d0b2e 30%, #151245 60%, #1a1550 100%)",
        }}
      />

      {/* 星星 */}
      {stars.map((s, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: s.x,
            top: s.y,
            width: s.size,
            height: s.size,
            borderRadius: "50%",
            background: "#ffffff",
            opacity: s.twinkle,
          }}
        />
      ))}

      {/* 顶部氛围光 */}
      <div
        style={{
          position: "absolute",
          top: -200,
          left: "50%",
          transform: "translateX(-50%)",
          width: 800,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(ellipse, rgba(99,80,200,0.12) 0%, transparent 70%)",
          filter: "blur(60px)",
        }}
      />

      {/* ═══ 主内容区（居中） ═══ */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: `60px ${sizes.paddingH}px ${sizes.paddingBottom}px`,
          transform: `translateY(${enterSlide}px)`,
        }}
      >
        {/* SKILL 编号 */}
        <div
          style={{
            opacity: skillOpacity,
            transform: `translateY(${skillSlide}px)`,
            fontSize: sizes.skillFont,
            fontWeight: 700,
            color: "#d4a843",
            letterSpacing: 8,
            textTransform: "uppercase",
            fontFamily: "'SF Mono', 'Fira Code', monospace",
            marginBottom: isLandscape ? 12 : 24,
          }}
        >
          SKILL {String(sceneIndex + 1).padStart(2, "0")}
        </div>

        {/* 主标题 */}
        {sceneTitle && (
          <h2
            style={{
              opacity: titleOpacity,
              transform: `scale(${titleScale * 0.08 + 0.92})`,
              fontSize: sizes.titleFont,
              fontWeight: 900,
              color: "#e8a838",
              textAlign: "center",
              margin: `0 0 ${isLandscape ? 12 : 20}px`,
              lineHeight: 1.3,
              fontFamily: "'SF Mono', 'Fira Code', 'PingFang SC', monospace",
              textShadow: "0 2px 20px rgba(232,168,56,0.3)",
            }}
          >
            {sceneTitle}
          </h2>
        )}

        {/* 副标题描述 */}
        {codeExample && (
          <div
            style={{
              opacity: subOpacity,
              fontSize: sizes.subFont,
              color: "rgba(180,160,220,0.9)",
              textAlign: "center",
              marginBottom: isLandscape ? 16 : 32,
              letterSpacing: 1,
            }}
          >
            {codeExample}
          </div>
        )}

        {/* 分割线 */}
        <div
          style={{
            width: lineWidth,
            height: 1,
            background: "linear-gradient(90deg, transparent, rgba(129,140,248,0.3), transparent)",
            marginBottom: isLandscape ? 20 : 36,
          }}
        />

        {/* ═══ 要点网格卡片 (2列) ═══ */}
        {keyPoints.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: sizes.gap,
              justifyContent: "center",
              maxWidth: sizes.maxCardWidth,
              width: "100%",
              border: "1px solid rgba(129,140,248,0.15)",
              borderRadius: 16,
              padding: sizes.cardPadding,
              background: "rgba(20,16,60,0.5)",
            }}
          >
            {keyPoints.map((point, i) => {
              const pointDelay = 25 + i * 8;
              const pointOpacity = interpolate(frame, [pointDelay, pointDelay + 8], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const pointScale = spring({
                frame: Math.max(0, frame - pointDelay),
                fps,
                config: { damping: 14, stiffness: 120 },
              });

              const dotColors = ["#4ade80", "#a78bfa", "#f59e0b", "#38bdf8"];
              const dotColor = dotColors[i % dotColors.length];

              return (
                <div
                  key={i}
                  style={{
                    opacity: pointOpacity,
                    transform: `scale(${pointScale * 0.05 + 0.95})`,
                    display: "flex",
                    alignItems: "center",
                    gap: sizes.gap,
                    width: "calc(50% - 6px)",
                    padding: sizes.pointPadding,
                    borderBottom: i < keyPoints.length - 2 ? "1px solid rgba(129,140,248,0.1)" : "none",
                  }}
                >
                  <div
                    style={{
                      width: sizes.dotSize,
                      height: sizes.dotSize,
                      borderRadius: "50%",
                      background: dotColor,
                      boxShadow: `0 0 8px ${dotColor}66`,
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      fontSize: sizes.pointFont,
                      color: "rgba(255,255,255,0.85)",
                      fontWeight: 500,
                      lineHeight: 1.3,
                    }}
                  >
                    {point}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* ═══ 数据徽标 ═══ */}
        {codeExample && (
          <div
            style={{
              marginTop: isLandscape ? 16 : 32,
              opacity: badgeOpacity,
              transform: `scale(${badgeScale * 0.05 + 0.95})`,
            }}
          >
            <div
              style={{
                padding: isLandscape ? "8px 20px" : "10px 28px",
                borderRadius: 20,
                border: "1px solid rgba(129,140,248,0.3)",
                background: "rgba(129,140,248,0.08)",
                fontSize: sizes.badgeFont,
                color: "rgba(180,170,230,0.9)",
                fontFamily: "'SF Mono', monospace",
                letterSpacing: 1,
              }}
            >
              ✦ {codeExample.length > 30 ? codeExample.slice(0, 30) + "…" : codeExample}
            </div>
          </div>
        )}
      </div>

      {/* ═══ 字幕区 ═══ */}
      <div
        style={{
          position: "absolute",
          bottom: sizes.captionBottom,
          left: 0,
          right: 0,
          padding: `0 ${sizes.paddingH}px`,
          textAlign: "center",
          opacity: narrationOpacity,
        }}
      >
        <p
          style={{
            fontSize: sizes.captionFont,
            color: "#ffffff",
            fontWeight: 600,
            lineHeight: 1.5,
            margin: 0,
            textShadow: "0 2px 12px rgba(0,0,0,0.8)",
          }}
        >
          {narration}
        </p>
      </div>

      {/* ═══ 顶部进度条 ═══ */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: "rgba(255,255,255,0.05)",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${interpolate(frame, [0, durationInFrames], [
              (sceneIndex / totalScenes) * 100,
              ((sceneIndex + 1) / totalScenes) * 100,
            ], { extrapolateRight: "clamp" })}%`,
            background: "linear-gradient(90deg, #d4a843, #e8a838)",
            borderRadius: "0 2px 2px 0",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
