import json
import os
import unittest
import uuid
from unittest.mock import AsyncMock

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core import db as db_module


class ImageFallbackMigrationSqlTests(unittest.TestCase):
    def test_upgrade_statements_cover_all_columns_and_sensitive_json_cleanup(self):
        statements = db_module._postgres_upgrade_statements()
        sql = "\n".join(statements).lower()

        expected_columns = [
            "fallback_enabled",
            "fallback_priority",
            "capabilities",
            "access_token_hash",
            "degraded",
            "requested_model_name",
            "actual_model_name",
            "fallback_attempts",
        ]
        for column in expected_columns:
            with self.subTest(column=column):
                self.assertIn(f"add column if not exists {column}", sql)

        self.assertIn("shared_config::jsonb", sql)
        self.assertIn("::json", sql)
        self.assertIn("#- '{image_model_config,api_key}'", sql)
        self.assertIn("#- '{image_model_config,base_url}'", sql)

    def test_upgrade_statements_are_plain_executable_sql(self):
        statements = db_module._postgres_upgrade_statements()

        self.assertIsInstance(statements, tuple)
        self.assertTrue(statements)
        self.assertTrue(all(isinstance(statement, str) and statement.strip() for statement in statements))
        self.assertTrue(all("add column" in statement.lower() or "update batch_tasks" in statement.lower()
                            for statement in statements))


class ImageFallbackMigrationExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_upgrade_statements_compile_for_postgres_and_execute(self):
        connection = AsyncMock()
        statements = db_module._postgres_upgrade_statements()

        for statement in statements:
            compiled = str(text(statement).compile(dialect=postgresql.dialect()))
            self.assertTrue(compiled.strip())
            await connection.execute(text(statement))

        self.assertEqual(connection.execute.await_count, len(statements))


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL 未配置，跳过独立 PostgreSQL 幂等迁移集成测试",
)
class ImageFallbackMigrationPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_is_idempotent_and_only_removes_sensitive_model_paths(self):
        database_url = TEST_DATABASE_URL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        engine = create_async_engine(database_url, poolclass=NullPool)
        schema = f"fallback_test_{uuid.uuid4().hex}"
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await self._create_legacy_tables(conn)
                await self._insert_legacy_tasks(conn)

                for _ in range(2):
                    for statement in db_module._postgres_upgrade_statements():
                        await conn.execute(text(statement))

                rows = (
                    await conn.execute(text(
                        "SELECT id, shared_config FROM batch_tasks ORDER BY id"
                    ))
                ).all()
                configs = {str(row.id): row.shared_config for row in rows}

                sensitive = configs["00000000-0000-0000-0000-000000000001"]
                self.assertEqual(
                    sensitive["image_model_config"],
                    {
                        "id": "model-1",
                        "name": "可见模型",
                        "model_name": "image-v1",
                    },
                )
                self.assertEqual(sensitive["aspect_ratio"], "3:4")
                self.assertEqual(configs["00000000-0000-0000-0000-000000000002"], {})
                self.assertEqual(
                    configs["00000000-0000-0000-0000-000000000003"],
                    {"mode": "template"},
                )
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await engine.dispose()

    async def _create_legacy_tables(self, conn):
        statements = [
            "CREATE TABLE users (id UUID PRIMARY KEY, username VARCHAR(50), created_at TIMESTAMPTZ)",
            "CREATE TABLE user_preferences (id UUID PRIMARY KEY)",
            "CREATE TABLE image_model_configs (id UUID PRIMARY KEY)",
            "CREATE TABLE batch_tasks (id UUID PRIMARY KEY, shared_config JSON NOT NULL)",
            "CREATE TABLE batch_task_items (id UUID PRIMARY KEY)",
        ]
        for statement in statements:
            await conn.execute(text(statement))

    async def _insert_legacy_tasks(self, conn):
        payloads = [
            (
                "00000000-0000-0000-0000-000000000001",
                {
                    "mode": "custom",
                    "aspect_ratio": "3:4",
                    "image_model_config": {
                        "id": "model-1",
                        "name": "可见模型",
                        "model_name": "image-v1",
                        "api_key": "redacted-test-secret",
                        "base_url": "https://sensitive.example.test",
                    },
                },
            ),
            ("00000000-0000-0000-0000-000000000002", {}),
            ("00000000-0000-0000-0000-000000000003", {"mode": "template"}),
        ]
        for task_id, shared_config in payloads:
            await conn.execute(
                text(
                    "INSERT INTO batch_tasks (id, shared_config) "
                    "VALUES (CAST(:id AS UUID), CAST(:shared_config AS JSON))"
                ),
                {"id": task_id, "shared_config": json.dumps(shared_config)},
            )
