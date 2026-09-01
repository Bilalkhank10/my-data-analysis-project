import asyncio
import json
import unittest

import httpx

from openrouter_client import (
    NoCompatibleEndpoint,
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    estimate_cost,
    is_endpoint_error,
    parse_structured_content,
)


class OpenRouterClientTests(unittest.TestCase):
    def test_mocked_structured_chat_embeddings_and_key_status(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers.get("authorization"), "Bearer sk-or-test-placeholder")
            if request.url.path.endswith("/key"):
                return httpx.Response(200, json={"data": {"label": "test", "limit": 1, "usage": 0.1}})
            if request.url.path.endswith("/embeddings"):
                body = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "id": "emb-1",
                        "data": [
                            {"index": index, "embedding": [float(index + 1), 0.5]}
                            for index, _ in enumerate(body["input"])
                        ],
                        "usage": {"prompt_tokens": 10, "total_tokens": 10, "cost": 0.001},
                    },
                )
            body = json.loads(request.content)
            self.assertEqual(body["response_format"]["type"], "json_schema")
            self.assertTrue(body["provider"]["require_parameters"])
            self.assertEqual(body["plugins"], [{"id": "response-healing"}])
            return httpx.Response(
                200,
                json={
                    "id": "gen-1",
                    "choices": [{"message": {"content": '{"ok":true}'}}],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 5,
                        "total_tokens": 25,
                        "cost": 0.002,
                    },
                },
            )

        async def run():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as http_client:
                config = OpenRouterConfig(
                    api_key="sk-or-test-placeholder",
                    base_url="https://openrouter.test/api/v1",
                    max_cost_usd=1,
                )
                client = OpenRouterClient(config, client=http_client)
                status = await client.key_status()
                self.assertTrue(status["valid"])
                vectors, emb_usage, _ = await client.embeddings(["one", "two"])
                self.assertEqual(len(vectors), 2)
                self.assertEqual(emb_usage.total_tokens, 10)
                data, usage, _ = await client.chat_json(
                    messages=[{"role": "user", "content": "test"}],
                    schema_name="test_schema",
                    schema={
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                    max_tokens=32,
                )
                self.assertTrue(data["ok"])
                self.assertEqual(usage.total_tokens, 25)
                public = config.public_dict()
                self.assertNotIn("api_key", public)
                self.assertNotIn("sk-or-test-placeholder", json.dumps(public))

        asyncio.run(run())
        self.assertEqual(len(requests), 3)

    def test_parameter_routing_falls_back_to_json_object(self):
        payloads = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            payloads.append(body)
            if body.get("response_format", {}).get("type") == "json_schema":
                return httpx.Response(
                    404,
                    json={
                        "error": {
                            "message": "No endpoints found that can handle the requested parameters."
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "gen-fallback",
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 3,
                        "total_tokens": 13,
                        "cost": 0.001,
                    },
                },
            )

        async def run():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as http_client:
                client = OpenRouterClient(
                    OpenRouterConfig(
                        api_key="sk-or-test-placeholder",
                        base_url="https://openrouter.test/api/v1",
                        max_cost_usd=1,
                    ),
                    client=http_client,
                )
                data, _, _ = await client.chat_json(
                    messages=[{"role": "user", "content": "test"}],
                    schema_name="test",
                    schema={
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                    max_tokens=32,
                )
                self.assertTrue(data["ok"])

        asyncio.run(run())
        self.assertGreaterEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["response_format"]["type"], "json_schema")
        self.assertTrue(
            any(
                item.get("response_format", {}).get("type") == "json_object"
                for item in payloads
            )
        )
        self.assertTrue(
            any("plugins" not in item for item in payloads[1:]),
            "fallback payloads must drop the response-healing plugin",
        )

    def test_tolerant_structured_content_parser(self):
        self.assertEqual(parse_structured_content('```json\n{"ok": true}\n```'), {"ok": True})
        self.assertEqual(
            parse_structured_content('Here is the result:\n{"ok": true,}'),
            {"ok": True},
        )
        self.assertEqual(
            parse_structured_content([{"type": "text", "text": '{"ok": true}'}]),
            {"ok": True},
        )
        self.assertEqual(
            parse_structured_content('"{\\"ok\\": true}"'),
            {"ok": True},
        )

    def test_truncated_response_has_actionable_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "gen-truncated",
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": '{"ok": true'},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 10,
                        "total_tokens": 20,
                        "cost": 0.001,
                    },
                },
            )

        async def run():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as http_client:
                client = OpenRouterClient(
                    OpenRouterConfig(
                        api_key="sk-or-test-placeholder",
                        base_url="https://openrouter.test/api/v1",
                        max_cost_usd=1,
                    ),
                    client=http_client,
                )
                with self.assertRaisesRegex(OpenRouterError, "truncated"):
                    await client.chat_json(
                        messages=[{"role": "user", "content": "test"}],
                        schema_name="test",
                        schema={
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                            "required": ["ok"],
                            "additionalProperties": False,
                        },
                        max_tokens=32,
                    )

        asyncio.run(run())

    def test_cost_estimator(self):
        self.assertAlmostEqual(
            estimate_cost("deepseek/deepseek-v4-flash-0731", 1_000_000, 1_000_000),
            2.25,
        )

    def test_endpoint_errors_from_alternate_body_shapes(self):
        bodies = [
            (
                404,
                {"error": "No endpoints found that can handle the requested parameters."},
            ),
            (
                400,
                {
                    "error": {
                        "message": "Provider returned error",
                        "metadata": {
                            "raw": "No endpoints found that can handle the requested parameters."
                        },
                    }
                },
            ),
            (
                404,
                {"error": {"message": "No allowed providers are available for the selected model"}},
            ),
        ]

        for status, payload in bodies:
            def handler(request: httpx.Request, body=payload, code=status) -> httpx.Response:
                return httpx.Response(code, json=body)

            async def run():
                transport = httpx.MockTransport(handler)
                async with httpx.AsyncClient(transport=transport) as http_client:
                    client = OpenRouterClient(
                        OpenRouterConfig(
                            api_key="sk-or-test-placeholder",
                            base_url="https://openrouter.test/api/v1",
                            max_cost_usd=1,
                            allow_parameter_fallback=False,
                        ),
                        client=http_client,
                    )
                    with self.assertRaises(NoCompatibleEndpoint):
                        await client.chat_json(
                            messages=[{"role": "user", "content": "test"}],
                            schema_name="test",
                            schema={
                                "type": "object",
                                "properties": {"ok": {"type": "boolean"}},
                                "required": ["ok"],
                                "additionalProperties": False,
                            },
                            max_tokens=32,
                        )

            asyncio.run(run())

        self.assertTrue(is_endpoint_error("No endpoints found (HTTP 404)"))
        self.assertTrue(is_endpoint_error(OpenRouterError("No allowed providers")))
        self.assertTrue(is_endpoint_error("missing", 404))
        self.assertFalse(is_endpoint_error("rate limited", 429))


if __name__ == "__main__":
    unittest.main()
