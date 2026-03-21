import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

interface TitleSceneProps {
  title: string;
}

/**
 * 开场标题场景 — 逐字弹入 + 光效扩散 + 装饰动画
 * 支持 9:16 竖屏 和 16:9 横屏 自适应布局
 */
export const TitleScene: React.FC<TitleSceneProps> = ({ title }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const isLandscape = width > height;
  const chars = title.split("");

  // 响应式尺寸
  const sizes = isLandscape
    ? { padBottom: 120, titleFont: 52, subFont: 22, subBottom: 100, maxWidth: 900 }
    : { padBottom: 400, titleFont: 72, subFont: 28, subBottom: 500, maxWidth: 900 };

  // ═══════════ 背景脉冲 ═══════════
  const pulseScale = 1 + Math.sin(frame * 0.05) * 0.1;
  const pulseOpacity = interpolate(frame, [0, 20], [0, 0.5], {
    extrapolateRight: "clamp",
  });

  // ═══════════ 装饰圆环扩散 ═══════════
  const ringScale = interpolate(frame, [10, 60], [0.5, 2.5], {
    extrapolateRight: "clamp",
  });
  const ringOpacity = interpolate(frame, [10, 40, 60], [0, 0.4, 0], {
    extrapolateRight: "clamp",
  });

  // ═══════════ 副标题淡入 ═══════════
  const subtitleDelay = chars.length * 2 + 10;
  const subtitleOpacity = interpolate(frame, [subtitleDelay, subtitleDelay + 15], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subtitleSlide = interpolate(frame, [subtitleDelay, subtitleDelay + 15], [20, 0], {
    extrapolateRight: "clamp",
  });

  // ═══════════ 场景退出 ═══════════
  const exitStart = durationInFrames - 15;
  const exitOpacity = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = interpolate(frame, [exitStart, durationInFrames], [1, 0.95], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ═══════════ 浮动粒子 ═══════════
  const particles = Array.from({ length: 12 }, (_, i) => ({
    x: width / 2 + Math.cos(i * 0.52 + frame * 0.01) * (150 + i * 30),
    y: height / 2 + Math.sin(i * 0.73 + frame * 0.015) * (100 + i * 25),
    size: 2 + Math.sin(frame * 0.05 + i) * 1.5,
    opacity: 0.1 + Math.sin(frame * 0.03 + i * 2) * 0.08,
  }));

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: `60px 60px ${sizes.padBottom}px`,
        opacity: exitOpacity,
        transform: `scale(${exitScale})`,
      }}
    >
      {/* 背景脉冲光圈 */}
      <div
        style={{
          position: "absolute",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%)",
          opacity: pulseOpacity,
          transform: `scale(${pulseScale})`,
          filter: "blur(50px)",
        }}
      />

      {/* 扩散圆环 */}
      <div
        style={{
          position: "absolute",
          width: 300,
          height: 300,
          borderRadius: "50%",
          border: "2px solid rgba(129,140,248,0.3)",
          opacity: ringOpacity,
          transform: `scale(${ringScale})`,
        }}
      />

      {/* 浮动粒子 */}
      {particles.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: p.x,
            top: p.y,
            width: p.size,
            height: p.size,
            borderRadius: "50%",
            background: "#818cf8",
            opacity: p.opacity,
          }}
        />
      ))}

      {/* 主标题 — 逐字弹入 */}
      <div
        style={{
          textAlign: "center",
          zIndex: 1,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          maxWidth: sizes.maxWidth,
          gap: 0,
        }}
      >
        {chars.map((char, i) => {
          const charDelay = i * 2;
          const charScale = spring({
            frame: Math.max(0, frame - charDelay),
            fps,
            config: { damping: 12, stiffness: 150 },
          });
          const charOpacity = interpolate(frame, [charDelay, charDelay + 5], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const charRotate = interpolate(frame, [charDelay, charDelay + 8], [-5, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          return (
            <span
              key={i}
              style={{
                fontSize: sizes.titleFont,
                fontWeight: 800,
                color: "#ffffff",
                lineHeight: 1.3,
                textShadow: "0 4px 25px rgba(99,102,241,0.6), 0 0 60px rgba(129,140,248,0.2)",
                display: "inline-block",
                opacity: charOpacity,
                transform: `scale(${charScale}) rotate(${charRotate}deg)`,
              }}
            >
              {char === " " ? "\u00A0" : char}
            </span>
          );
        })}
      </div>

      {/* 装饰线 + 副标题 */}
      <div
        style={{
          position: "absolute",
          bottom: sizes.subBottom,
          opacity: subtitleOpacity,
          transform: `translateY(${subtitleSlide}px)`,
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: interpolate(frame, [subtitleDelay, subtitleDelay + 20], [0, 80], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            height: 4,
            background: "linear-gradient(90deg, #818cf8, #c084fc)",
            borderRadius: 2,
            margin: "0 auto 16px",
          }}
        />
        <p
          style={{
            fontSize: sizes.subFont,
            color: "rgba(255,255,255,0.6)",
            margin: 0,
            letterSpacing: 4,
          }}
        >
          AI 知识分享
        </p>
      </div>
    </AbsoluteFill>
  );
};
