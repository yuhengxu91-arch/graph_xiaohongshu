/**
 * Remotion 渲染 HTTP 服务
 * 
 * 接收来自 Python FastAPI 的渲染请求，调用 Remotion 渲染引擎，
 * 返回 MP4 文件下载链接。
 * 
 * 端口: 3100
 */
import express from "express";
import path from "path";
import fs from "fs";
import { v4 as uuidv4 } from "uuid";
import {
  executeRender,
  getTask,
  setTask,
  type RenderRequest,
  type RenderTask,
} from "./render-video";

const app = express();
const PORT = process.env.REMOTION_PORT || 3100;

// 输出目录
const OUTPUT_DIR = path.resolve(__dirname, "..", "..", "static", "videos");
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// 挂载静态文件服务 — 让 Remotion 可以通过 HTTP 访问 TTS 音频
const STATIC_DIR = path.resolve(__dirname, "..", "..", "static");
app.use("/static", express.static(STATIC_DIR));

app.use(express.json({ limit: "10mb" }));

/**
 * GET /health — 健康检查
 */
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "remotion-renderer",
    uptime: process.uptime(),
  });
});

/**
 * POST /render — 提交渲染任务
 * 
 * Body: {
 *   compositionId: "KnowledgeVideo",
 *   inputProps: { title, scenes },
 *   width?: 1080,
 *   height?: 1920
 * }
 */
app.post("/render", (req, res) => {
  const request: RenderRequest = req.body;

  if (!request.compositionId || !request.inputProps) {
    res.status(400).json({
      error: "Missing compositionId or inputProps",
    });
    return;
  }

  const taskId = uuidv4();
  const task: RenderTask = {
    taskId,
    status: "queued",
    progress: 0,
    startedAt: Date.now(),
  };

  setTask(taskId, task);

  // 异步执行渲染（不阻塞响应）
  executeRender(taskId, request, OUTPUT_DIR).catch((err) => {
    console.error(`[Server] Render error for ${taskId}:`, err);
  });

  res.json({ taskId, status: "queued" });
});

/**
 * GET /status/:taskId — 查询渲染进度
 */
app.get("/status/:taskId", (req, res) => {
  const task = getTask(req.params.taskId);
  if (!task) {
    res.status(404).json({ error: "Task not found" });
    return;
  }

  res.json({
    taskId: task.taskId,
    status: task.status,
    progress: task.progress,
    error: task.error,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
  });
});

/**
 * GET /download/:taskId — 下载渲染完成的 MP4
 */
app.get("/download/:taskId", (req, res) => {
  const task = getTask(req.params.taskId);
  if (!task) {
    res.status(404).json({ error: "Task not found" });
    return;
  }

  if (task.status !== "completed" || !task.outputPath) {
    res.status(400).json({
      error: "Render not completed",
      status: task.status,
      progress: task.progress,
    });
    return;
  }

  if (!fs.existsSync(task.outputPath)) {
    res.status(404).json({ error: "Output file not found" });
    return;
  }

  res.download(task.outputPath, `video_${req.params.taskId}.mp4`);
});

/**
 * 启动服务
 */
app.listen(PORT, () => {
  console.log(`\n🎬 Remotion Renderer Service`);
  console.log(`   Port: ${PORT}`);
  console.log(`   Output: ${OUTPUT_DIR}`);
  console.log(`   Health: http://localhost:${PORT}/health\n`);
});
