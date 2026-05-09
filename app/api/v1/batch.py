"""
批量生成 API 路由
提供批量生成提交、进度查询、SSE 推送、ZIP 下载、失败重试等接口
"""
import asyncio
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.dependencies.auth import get_current_user_optional
from app.models.user import User
from app.services.brand_service import brand_service
from app.services.batch_service import batch_service
from app.services.image_model_service import image_model_service
from app.services.profile_service import profile_service

router = APIRouter(prefix="/poster/batch", tags=["Poster Batch"])


# ======================== 请求/响应模型 ========================

class BatchItemInput(BaseModel):
    """单条批量生成内容"""
    title: str = Field("", description="主标题（可选）")
    subtitle: str = Field("", description="副标题（可选）")
    prompt: str = Field(..., description="画面描述/提示词（必填）", min_length=1, max_length=500)


class BatchGenerateRequest(BaseModel):
    """批量生成请求"""
    mode: str = Field("custom", description="生成模式: custom / template")
    aspect_ratio: str = Field("3:4", description="统一输出比例")
    color_tone: Optional[str] = Field(None, description="全局色调偏好")
    style_tags: Optional[List[str]] = Field(None, description="全局风格标签")
    template_index: Optional[int] = Field(None, description="模板索引（mode=template 时使用）")
    series_mode: bool = Field(False, description="是否启用系列风格一致性")
    items: List[BatchItemInput] = Field(..., description="生成内容列表", min_length=1, max_length=50)


class BatchGenerateResponse(BaseModel):
    """批量生成响应"""
    success: bool
    task_id: Optional[str] = None
    total_count: int = 0
    mode: str = "batch"
    error: Optional[str] = None


class BatchItemStatus(BaseModel):
    """子任务状态"""
    order_index: int
    status: str
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    title: str = ""
    subtitle: str = ""


class BatchStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    running_count: int
    series_mode: bool = False
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    items: List[BatchItemStatus]


# ======================== 接口 ========================

@router.post(
    "/generate",
    response_model=BatchGenerateResponse,
    summary="提交批量生成任务",
)
async def batch_generate(
    req: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_async_session),
):
    """
    提交批量生成任务

    - 立即返回 task_id，后台异步执行生成
    - 启用 series_mode 时，首图先同步生成作为风格锚点，后续图片并发生成
    - 最大并发数: 3
    """
    try:
        brand_kit = None
        image_provider = None
        image_model_config = None
        if current_user:
            kit = await brand_service.get_brand_kit(db, user_id=current_user.id)
            if kit:
                brand_kit = brand_service.serialize(kit)
            image_provider = await profile_service.get_user_image_provider(
                db,
                user_id=current_user.id,
            )
            image_model_config = await profile_service.get_user_image_model_config(
                db,
                user_id=current_user.id,
            )

        if not image_provider and not image_model_config:
            default_model = await image_model_service.get_default_config(db)
            if default_model:
                image_model_config = image_model_service.runtime_config(default_model)

        # 构建共享配置
        shared_config = {
            "mode": req.mode,
            "aspect_ratio": req.aspect_ratio,
            "color_tone": req.color_tone,
            "style_tags": req.style_tags,
            "template_index": req.template_index,
            "series_mode": req.series_mode,
            "brand_kit": brand_kit,
            "image_provider": image_provider,
            "image_model_config": image_model_config,
        }

        # 转换 items
        items = [item.model_dump() for item in req.items]

        # 创建任务
        result = await batch_service.create_batch_task(
            items,
            shared_config,
            user_id=current_user.id if current_user else None,
        )

        # 后台异步执行
        background_tasks.add_task(batch_service.run_batch_task, result["task_id"])

        return BatchGenerateResponse(
            success=True,
            task_id=result["task_id"],
            total_count=result["total_count"],
            mode="batch",
        )

    except Exception as e:
        return BatchGenerateResponse(
            success=False,
            error=f"创建批量任务失败: {str(e)}",
        )


@router.get(
    "/{task_id}/status",
    response_model=BatchStatusResponse,
    summary="查询批量任务进度",
)
async def get_batch_status(task_id: str):
    """
    查询批量生成任务的详细进度

    返回整体状态、各子任务的生成状态和结果图片 URL
    """
    status = batch_service.get_batch_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return status


@router.get(
    "/{task_id}/stream",
    summary="SSE 实时推送生成进度",
)
async def stream_batch_status(task_id: str):
    """
    Server-Sent Events 实时推送批量任务进度

    前端通过 EventSource 监听，每 2 秒发送一次当前状态
    任务完成后自动关闭连接
    """
    import json

    async def event_generator():
        max_polls = 300  # 最多轮询 10 分钟
        poll_count = 0

        while poll_count < max_polls:
            status = batch_service.get_batch_status(task_id)
            if not status:
                yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
                break

            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"

            # 任务已完成
            if status["status"] in ("completed", "partial_failed", "failed"):
                break

            poll_count += 1
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{task_id}/download",
    summary="ZIP 打包下载所有成功图片",
)
async def download_batch(task_id: str):
    """
    将批量生成的所有成功图片打包为 ZIP 下载

    文件命名格式: 序号_标题.png
    """
    zip_buffer = batch_service.build_download_zip(task_id)
    if not zip_buffer:
        raise HTTPException(
            status_code=404,
            detail="任务不存在或尚无成功的图片可下载",
        )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=batch_{task_id[:8]}.zip",
        },
    )


@router.post(
    "/{task_id}/retry",
    summary="重试所有失败的子任务",
)
async def retry_failed(task_id: str):
    """
    重新生成批量任务中所有状态为 failed 的子任务

    重试时保留原有参数和系列风格锚定配置
    """
    result = await batch_service.retry_failed_items(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return result
