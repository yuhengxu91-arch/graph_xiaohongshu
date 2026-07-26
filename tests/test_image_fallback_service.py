import json
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services.image_fallback_service import (
    GenerationContext,
    GenerationOutcome,
    ImageFallbackService,
    ImageModelRef,
    derive_required_capabilities,
    resolve_runtime_config,
)
from app.services.image_generation_errors import ImageGenerationError
from app.services.image_model_service import ImageModelService


class ImageModelRefTests(unittest.TestCase):
    def test_config_reference_round_trips_without_secrets(self):
        config_id = uuid4()
        model_ref = ImageModelRef(
            source="config",
            display_name="公共 GPT Image",
            config_id=config_id,
        )

        payload = model_ref.to_dict()
        restored = ImageModelRef.from_dict(payload)

        self.assertEqual(restored, model_ref)
        serialized = json.dumps(payload)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("base_url", serialized)

    def test_builtin_reference_round_trips_with_provider(self):
        model_ref = ImageModelRef(
            source="builtin",
            display_name="Gemini（系统内置）",
            provider="gemini",
        )

        self.assertEqual(ImageModelRef.from_dict(model_ref.to_dict()), model_ref)

    def test_invalid_reference_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            ImageModelRef(source="config", display_name="缺少配置 ID")
        with self.assertRaises(ValueError):
            ImageModelRef(source="builtin", display_name="缺少 provider")
        with self.assertRaises(ValueError):
            ImageModelRef(
                source="builtin",
                display_name="未知模型",
                provider="unknown",
            )


class RuntimeResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_reference_resolves_runtime_secret_only_at_execution(self):
        config_id = uuid4()
        config = SimpleNamespace(
            id=config_id,
            name="公共模型",
            provider_type="openai_image",
            base_url="https://images.example.test",
            model_name="gpt-image-2",
            api_key="secret-value",
            is_active=True,
        )

        with patch(
            "app.services.image_fallback_service.image_model_service.get_config",
            AsyncMock(return_value=config),
        ):
            runtime = await resolve_runtime_config(
                object(),
                ImageModelRef(
                    source="config",
                    display_name="公共模型",
                    config_id=config_id,
                ),
            )

        self.assertIsNone(runtime["provider_override"])
        self.assertEqual(runtime["image_model_config"]["api_key"], "secret-value")
        self.assertEqual(runtime["image_model_config"]["base_url"], "https://images.example.test")

    async def test_builtin_reference_resolves_to_provider_without_database_secret(self):
        runtime = await resolve_runtime_config(
            object(),
            ImageModelRef(
                source="builtin",
                display_name="豆包 Seedream",
                provider="doubao",
            ),
        )

        self.assertEqual(runtime["provider_override"], "doubao")
        self.assertIsNone(runtime["image_model_config"])


class FallbackCandidateTests(unittest.IsolatedAsyncioTestCase):
    def test_capability_matching_is_conservative_but_empty_ratios_allow_adaptation(self):
        service = ImageModelService()
        self.assertTrue(
            service._supports_capabilities(
                {"text_to_image": True, "aspect_ratios": []},
                {"text_to_image": True, "aspect_ratio": "3:4"},
            )
        )
        self.assertFalse(
            service._supports_capabilities(
                {"text_to_image": True},
                {"text_to_image": True, "aspect_ratio": "3:4"},
            )
        )
        self.assertFalse(
            service._supports_capabilities(
                {"aspect_ratios": []},
                {"unknown_capability": True},
            )
        )

    async def test_candidate_query_filters_and_orders_without_selecting_secrets(self):
        service = ImageModelService()
        primary_id = uuid4()
        candidate_id = uuid4()

        class MappingResult:
            def mappings(self):
                return self

            def all(self):
                return [{
                    "id": candidate_id,
                    "name": "安全候选",
                    "provider_type": "openai_image",
                    "capabilities": {
                        "text_to_image": True,
                        "aspect_ratios": ["3:4"],
                    },
                }]

        class CapturingDb:
            statement = None

            async def execute(self, statement):
                self.statement = statement
                return MappingResult()

        db = CapturingDb()
        refs = await service.list_fallback_model_refs(
            db,
            primary_ref=ImageModelRef(
                source="config",
                display_name="主模型",
                config_id=primary_id,
            ),
            required_capabilities={
                "text_to_image": True,
                "aspect_ratio": "3:4",
            },
        )

        sql = str(
            db.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        selected_columns = sql.partition("\nfrom ")[0]
        self.assertIn("image_model_configs.is_active = true", sql)
        self.assertIn("image_model_configs.fallback_enabled = true", sql)
        self.assertIn("image_model_configs.fallback_priority > 0", sql)
        self.assertIn(f"image_model_configs.id != '{primary_id}'", sql)
        self.assertIn(
            "order by image_model_configs.fallback_priority asc, "
            "image_model_configs.sort_order asc, "
            "image_model_configs.created_at asc",
            sql,
        )
        self.assertNotIn("api_key", selected_columns)
        self.assertNotIn("base_url", selected_columns)
        self.assertNotIn("model_name", selected_columns)
        self.assertNotIn("fallback_priority", selected_columns)
        self.assertNotIn("sort_order", selected_columns)
        self.assertNotIn("created_at", selected_columns)
        self.assertEqual([ref.display_name for ref in refs], ["安全候选"])

    async def test_candidates_are_sorted_and_filtered_by_primary_state_and_capability(self):
        service = ImageModelService()
        now = datetime.now(timezone.utc)
        primary_id = uuid4()

        def row(
            name,
            priority,
            sort_order,
            created_offset,
            *,
            capabilities=None,
        ):
            return {
                "id": uuid4(),
                "name": name,
                "provider_type": "openai_image",
                "fallback_priority": priority,
                "sort_order": sort_order,
                "created_at": now + timedelta(seconds=created_offset),
                "capabilities": capabilities
                or {"text_to_image": True, "aspect_ratios": ["3:4"]},
            }

        rows = [
            row(
                "能力不匹配",
                1,
                0,
                0,
                capabilities={"text_to_image": False, "aspect_ratios": ["3:4"]},
            ),
            row("备用 A1", 1, 1, 30),
            row("备用 A2", 1, 2, 10),
            row("备用 B", 2, 0, 20),
        ]

        result = SimpleNamespace(
            mappings=lambda: SimpleNamespace(all=lambda: rows),
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        refs = await service.list_fallback_model_refs(
            db,
            primary_ref=ImageModelRef(
                source="config",
                display_name="主模型",
                config_id=primary_id,
            ),
            required_capabilities={
                "text_to_image": True,
                "aspect_ratio": "3:4",
            },
        )

        self.assertEqual([ref.display_name for ref in refs], ["备用 A1", "备用 A2", "备用 B"])
        self.assertTrue(all(ref.source == "config" for ref in refs))


class CapabilityDerivationTests(unittest.TestCase):
    def test_text_and_reference_modes(self):
        self.assertEqual(
            derive_required_capabilities("custom", aspect_ratio="3:4"),
            {"text_to_image": True, "aspect_ratio": "3:4"},
        )
        self.assertEqual(
            derive_required_capabilities(
                "custom", reference_count=1, aspect_ratio="1:1"
            ),
            {"single_reference": True, "aspect_ratio": "1:1"},
        )
        self.assertEqual(
            derive_required_capabilities(
                "template", reference_count=3, aspect_ratio="9:16"
            ),
            {"multiple_references": True, "aspect_ratio": "9:16"},
        )

    def test_edit_modes_and_masks(self):
        for mode in ("edit", "style_transfer", "outpaint", "adapt"):
            self.assertEqual(
                derive_required_capabilities(mode, aspect_ratio="3:4"),
                {"image_edit": True, "aspect_ratio": "3:4"},
            )
        for mode in ("inpaint", "erase"):
            self.assertEqual(
                derive_required_capabilities(mode, aspect_ratio="3:4"),
                {
                    "image_edit": True,
                    "mask_edit": True,
                    "aspect_ratio": "3:4",
                },
            )

    def test_export_all_uses_each_item_shape(self):
        self.assertEqual(
            derive_required_capabilities(
                "export_all",
                reference_count=2,
                aspect_ratio="16:9",
            ),
            {"multiple_references": True, "aspect_ratio": "16:9"},
        )


class OrderedFallbackCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.primary = ImageModelRef(
            source="config",
            display_name="主模型",
            config_id=uuid4(),
        )
        self.backup_a = ImageModelRef(
            source="config",
            display_name="备用 A",
            config_id=uuid4(),
        )
        self.backup_b = ImageModelRef(
            source="config",
            display_name="备用 B",
            config_id=uuid4(),
        )
        self.context = GenerationContext(
            chain_id="chain-1",
            task_id="task-1",
            item_id="item-1",
            user_id="user-1",
        )

    def retryable(self, category="server_error"):
        return ImageGenerationError(
            category,
            "safe",
            retryable=True,
            provider_status=503,
        )

    def permanent(self):
        return ImageGenerationError(
            "auth",
            "safe",
            retryable=False,
            provider_status=401,
        )

    def service(self, candidates):
        async def load_candidates(primary_ref, required):
            return list(candidates)

        async def resolve(model_ref):
            return {"display_name": model_ref.display_name}

        return ImageFallbackService(
            candidate_loader=load_candidates,
            runtime_resolver=resolve,
        )

    async def test_primary_success_does_not_query_candidates(self):
        candidate_loader = AsyncMock(return_value=[self.backup_a])
        resolver = AsyncMock(return_value={"display_name": "主模型"})
        invoke = AsyncMock(return_value="image")
        service = ImageFallbackService(
            candidate_loader=candidate_loader,
            runtime_resolver=resolver,
        )

        outcome = await service.generate(
            primary_ref=self.primary,
            required_capabilities={"text_to_image": True},
            invoke=invoke,
            context=self.context,
        )

        self.assertEqual(
            outcome,
            GenerationOutcome(
                image_base64="image",
                degraded=False,
                requested_model_name="主模型",
                actual_model_name="主模型",
                fallback_attempts=0,
            ),
        )
        candidate_loader.assert_not_awaited()

    async def test_retryable_primary_failure_uses_ordered_candidate(self):
        service = self.service([self.backup_a, self.backup_b])
        calls = []

        async def invoke(runtime):
            calls.append(runtime["display_name"])
            if len(calls) < 3:
                raise self.retryable()
            return "backup-image"

        outcome = await service.generate(
            primary_ref=self.primary,
            required_capabilities={"text_to_image": True},
            invoke=invoke,
            context=self.context,
        )

        self.assertEqual(calls, ["主模型", "备用 A", "备用 B"])
        self.assertEqual(outcome.image_base64, "backup-image")
        self.assertTrue(outcome.degraded)
        self.assertEqual(outcome.requested_model_name, "主模型")
        self.assertEqual(outcome.actual_model_name, "备用 B")
        self.assertEqual(outcome.fallback_attempts, 2)

    async def test_non_retryable_error_stops_immediately(self):
        service = self.service([self.backup_a])
        invoke = AsyncMock(side_effect=self.permanent())
        with self.assertRaises(ImageGenerationError) as raised:
            await service.generate(
                primary_ref=self.primary,
                required_capabilities={"text_to_image": True},
                invoke=invoke,
                context=self.context,
            )
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(invoke.await_count, 1)

    async def test_candidate_is_revalidated_before_call(self):
        calls = 0

        async def load_candidates(primary_ref, required):
            nonlocal calls
            calls += 1
            return [self.backup_a, self.backup_b] if calls == 1 else [self.backup_b]

        async def resolve(model_ref):
            return {"display_name": model_ref.display_name}

        service = ImageFallbackService(
            candidate_loader=load_candidates,
            runtime_resolver=resolve,
        )
        invoked = []

        async def invoke(runtime):
            invoked.append(runtime["display_name"])
            if runtime["display_name"] == "主模型":
                raise self.retryable()
            return "image"

        outcome = await service.generate(
            primary_ref=self.primary,
            required_capabilities={"text_to_image": True},
            invoke=invoke,
            context=self.context,
        )

        self.assertEqual(invoked, ["主模型", "备用 B"])
        self.assertEqual(outcome.actual_model_name, "备用 B")
        self.assertEqual(outcome.fallback_attempts, 1)

    async def test_all_candidates_fail_with_last_safe_error(self):
        last_error = ImageGenerationError(
            "timeout", "last-safe", retryable=True
        )
        service = self.service([self.backup_a])
        errors = iter([self.retryable(), last_error])

        async def invoke(runtime):
            raise next(errors)

        with self.assertRaises(ImageGenerationError) as raised:
            await service.generate(
                primary_ref=self.primary,
                required_capabilities={"text_to_image": True},
                invoke=invoke,
                context=self.context,
            )
        self.assertIs(raised.exception, last_error)

    async def test_cancellation_stops_primary_candidate_and_switching(self):
        for phase in ("primary", "switch", "candidate"):
            candidate_loader = AsyncMock(return_value=[self.backup_a])
            resolver = AsyncMock(
                side_effect=lambda ref: {"display_name": ref.display_name}
            )
            invoke_calls = 0

            async def invoke(runtime):
                nonlocal invoke_calls
                invoke_calls += 1
                if phase == "primary":
                    raise asyncio.CancelledError()
                if invoke_calls == 1:
                    raise self.retryable()
                if phase == "candidate":
                    raise asyncio.CancelledError()
                return "image"

            if phase == "switch":
                candidate_loader.side_effect = asyncio.CancelledError()

            service = ImageFallbackService(
                candidate_loader=candidate_loader,
                runtime_resolver=resolver,
            )
            with self.assertRaises(asyncio.CancelledError):
                await service.generate(
                    primary_ref=self.primary,
                    required_capabilities={"text_to_image": True},
                    invoke=invoke,
                    context=self.context,
                )
