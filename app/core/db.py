"""
数据库连接模块
配置 SQLAlchemy AsyncSession
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 声明基类
Base = declarative_base()


def _postgres_upgrade_statements() -> tuple[str, ...]:
    """返回 PostgreSQL 旧库升级所需的幂等 SQL。"""
    return (
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE user_preferences "
        "ADD COLUMN IF NOT EXISTS image_model_config_id UUID",
        "ALTER TABLE image_model_configs "
        "ADD COLUMN IF NOT EXISTS fallback_enabled BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE image_model_configs "
        "ADD COLUMN IF NOT EXISTS fallback_priority INTEGER",
        "ALTER TABLE image_model_configs "
        "ADD COLUMN IF NOT EXISTS capabilities JSON NOT NULL DEFAULT '{}'::json",
        "ALTER TABLE batch_tasks "
        "ADD COLUMN IF NOT EXISTS access_token_hash VARCHAR(128)",
        "ALTER TABLE batch_task_items "
        "ADD COLUMN IF NOT EXISTS degraded BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE batch_task_items "
        "ADD COLUMN IF NOT EXISTS requested_model_name VARCHAR(100)",
        "ALTER TABLE batch_task_items "
        "ADD COLUMN IF NOT EXISTS actual_model_name VARCHAR(100)",
        "ALTER TABLE batch_task_items "
        "ADD COLUMN IF NOT EXISTS fallback_attempts INTEGER NOT NULL DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS ix_image_model_configs_fallback_enabled "
        "ON image_model_configs (fallback_enabled)",
        "CREATE INDEX IF NOT EXISTS ix_image_model_configs_fallback_priority "
        "ON image_model_configs (fallback_priority)",
        "CREATE INDEX IF NOT EXISTS ix_batch_tasks_access_token_hash "
        "ON batch_tasks (access_token_hash)",
        """
        UPDATE batch_tasks
        SET shared_config = (
            shared_config::jsonb
            #- '{image_model_config,api_key}'
            #- '{image_model_config,base_url}'
        )::json
        WHERE shared_config::jsonb #> '{image_model_config,api_key}' IS NOT NULL
           OR shared_config::jsonb #> '{image_model_config,base_url}' IS NOT NULL
        """,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话
    用于 FastAPI 依赖注入
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库（创建表）
    """
    import app.models  # noqa: F401  # 确保所有模型已注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            for statement in _postgres_upgrade_statements():
                await conn.execute(text(statement))
            await _bootstrap_admin_role(conn)
    print("[DB] Database initialized")


async def _bootstrap_admin_role(conn) -> None:
    """仅在升级后没有启用管理员时，将旧系统管理员规则持久化一次。"""
    active_admin = await conn.scalar(text(
        "SELECT id FROM users "
        "WHERE is_admin = TRUE AND is_active = TRUE LIMIT 1"
    ))
    if active_admin is not None:
        return

    configured = [
        name.strip()
        for name in settings.admin_usernames.split(",")
        if name.strip()
    ]
    candidate_id = None
    if configured:
        placeholders = ", ".join(f":username_{index}" for index in range(len(configured)))
        params = {f"username_{index}": username for index, username in enumerate(configured)}
        candidate_id = await conn.scalar(text(
            "SELECT id FROM users "
            f"WHERE is_active = TRUE AND username IN ({placeholders}) "
            "ORDER BY created_at ASC LIMIT 1"
        ), params)

    if candidate_id is None:
        candidate_id = await conn.scalar(text(
            "SELECT id FROM users WHERE is_active = TRUE "
            "ORDER BY created_at ASC LIMIT 1"
        ))
    if candidate_id is not None:
        await conn.execute(
            text("UPDATE users SET is_admin = TRUE WHERE id = :user_id"),
            {"user_id": candidate_id},
        )


async def close_db() -> None:
    """
    关闭数据库连接
    """
    await engine.dispose()
    print("[DB] Database connection closed")
