import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

/**
 * 结尾 CTA 场景 — 多层动画 + 粒子爆发 + 弹性按钮
 * 支持 9:16 竖屏 和 16:9 横屏 自适应布局
 */
export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const isLandscape = width > height;

  // 响应式尺寸
  const sizes = isLandscape
    ? { padBottom: 120, iconSize: 70, titleFont: 40, subFont: 24, ctaFont: 26, ctaBottom: 80, ctaPadding: "16px 48px" }
    : { padBottom: 400, iconSize: 100, titleFont: 56, subFont: 30, ctaFont: 32, ctaBottom: 500, ctaPadding: "22px 64px" };

  // ═══════════ 图标弹入 + 持续摆动 ═══════════
  const iconScale = spring({
    frame,
    fps,
    config: { damping: 8, stiffness: 120 },
  });
  const iconWobble = Math.sin(frame * 0.08) * 5;

  // ═══════════ 文字逐行出现 ═══════════
  const line1Opacity = interpolate(frame, [12, 22], [0, 1], {
    extrapolateRight: "clamp",
  });
  const line1Slide = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const line2Opacity = interpolate(frame, [25, 35], [0, 1], {
    extrapolateRight: "clamp",
  });
  const line2Slide = spring({
    frame: Math.max(0, frame - 25),
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  // ═══════════ CTA 按钮 ═══════════
  const ctaScale = spring({
    frame: Math.max(0, frame - 40),
    fps,
    config: { damping: 10, stiffness: 150 },
  });
  const ctaGlow = 0.3 + Math.sin(frame * 0.1) * 0.2;

  // ═══════════ 粒子爆发 ═══════════
  const burstParticles = Array.from({ length: 16 }, (_, i) => {
    const angle = (i / 16) * Math.PI * 2;
    const distance = spring({
      frame,
      fps,
      config: { damping: 30, stiffness: 50 },
    }) * 200;
    return {
      x: width / 2 + Math.cos(angle) * distance,
      y: height * 0.42 + Math.sin(angle) * distance,
      opacity: interpolate(frame, [0, 10, 50], [0, 0.6, 0], {
        extrapolateRight: "clamp",
      }),
      size: 4 + Math.random() * 4,
    };
  });

  // ═══════════ 场景退出 ═══════════
  const exitStart = durationInFrames - 10;
  const exitOpacity = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: `60px 60px ${sizes.padBottom}px`,
        opacity: exitOpacity,
      }}
    >
      {/* 背景光效 */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(192,132,252,0.25) 0%, transparent 70%)",
          filter: "blur(60px)",
          transform: `scale(${1 + Math.sin(frame * 0.04) * 0.1})`,
        }}
      />

      {/* 粒子爆发 */}
      {burstParticles.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: p.x,
            top: p.y,
            width: p.size,
            height: p.size,
            borderRadius: "50%",
            background: i % 2 === 0 ? "#818cf8" : "#c084fc",
            opacity: p.opacity,
          }}
        />
      ))}

      {/* 点赞图标 — 持续摆动 */}
      <div
        style={{
          transform: `scale(${iconScale}) rotate(${iconWobble}deg)`,
          fontSize: sizes.iconSize,
          marginBottom: isLandscape ? 20 : 40,
          filter: "drop-shadow(0 0 20px rgba(192,132,252,0.4))",
        }}
      >
        👍
      </div>

      {/* 感谢文字 — 逐行弹入 */}
      <div style={{ textAlign: "center", zIndex: 1 }}>
        <h2
          style={{
            fontSize: sizes.titleFont,
            fontWeight: 700,
            color: "#ffffff",
            margin: "0 0 16px",
            opacity: line1Opacity,
            transform: `translateY(${interpolate(line1Slide, [0, 1], [30, 0])}px)`,
            textShadow: "0 4px 20px rgba(0,0,0,0.3)",
          }}
        >
          感谢观看
        </h2>
        <p
          style={{
            fontSize: sizes.subFont,
            color: "rgba(255,255,255,0.7)",
            margin: 0,
            opacity: line2Opacity,
            transform: `translateY(${interpolate(line2Slide, [0, 1], [20, 0])}px)`,
          }}
        >
          如果觉得有帮助，记得点赞收藏 ❤️
        </p>
      </div>

      {/* CTA 按钮 — 弹入 + 呼吸发光 */}
      <div
        style={{
          position: "absolute",
          bottom: sizes.ctaBottom,
          transform: `scale(${ctaScale})`,
        }}
      >
        <div
          style={{
            padding: sizes.ctaPadding,
            background: "linear-gradient(135deg, #818cf8, #c084fc)",
            borderRadius: 40,
            fontSize: sizes.ctaFont,
            fontWeight: 700,
            color: "#ffffff",
            boxShadow: `0 8px 40px rgba(129,140,248,${ctaGlow}), 0 0 60px rgba(192,132,252,${ctaGlow * 0.5})`,
            letterSpacing: 2,
          }}
        >
          ✨ 关注获取更多干货
        </div>
      </div>
    </AbsoluteFill>
  );
};
