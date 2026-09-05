from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest
from mcp.server.fastmcp import FastMCP

import dishboard_mcp.server as server


try:
    from mcp.server.fastmcp.exceptions import ToolError as FastMCPToolError
except Exception:  # pragma: no cover
    FastMCPToolError = ValueError


TOOL_ERROR = FastMCPToolError
ROOT = Path(__file__).resolve().parents[2]
CAFETERIA_SNAPSHOT = json.loads((ROOT / "demo/snapshots/cafeteria_kw36.json").read_text(encoding="utf-8"))
PATIENTEN_SNAPSHOT = json.loads((ROOT / "demo/snapshots/patienten_kw36.json").read_text(encoding="utf-8"))
STATUS = {
    "service": "dishboard",
    "api_version": "1.0.0",
    "time": "2026-09-05T21:40:00+02:00",
    "channels": [
        {
            "channel": "cafeteria",
            "profile_code": "staff_guest",
            "revision_id": "REV-CAF-KW36",
            "published": True,
            "week_start": "2026-08-31",
            "week_end": "2026-09-06",
        },
        {
            "channel": "patienten",
            "profile_code": "patient",
            "revision_id": "REV-PAT-KW36",
            "published": True,
            "week_start": "2026-08-31",
            "week_end": "2026-09-06",
        },
    ],
}
WEEKS_CAFETERIA = {
    "channel": "cafeteria",
    "weeks": [
        {
            "week_start": "2026-08-31",
            "week_end": "2026-09-06",
            "title": "KW 36",
            "workflow_state": "published",
            "status": "published",
        }
    ],
}
WEEK_PREVIEW = {
    "channel": "cafeteria",
    "week_start": "2026-08-31",
    "week_end": "2026-09-06",
    "workflow_state": "published",
    "status": "published",
    "title": "Vorschau KW36",
}
FHIR_DOCUMENT = {
    "resourceType": "Bundle",
    "type": "document",
    "id": "REV-CAF-KW36",
}
OPENAPI = {"openapi": "3.1.0"}


def mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v1/published/cafeteria":
        return httpx.Response(200, json=CAFETERIA_SNAPSHOT)
    if path == "/api/v1/published/patienten":
        return httpx.Response(200, json=PATIENTEN_SNAPSHOT)
    if path == "/api/v1/published/ghost":
        return httpx.Response(
            404,
            json={"error": "no_published_menu", "detail": "Ghost-Kanal ist nicht publiziert"},
        )
    if path.startswith("/api/v1/published/") and path.endswith("/today"):
        channel = path.split("/")[3]
        if channel == "cafeteria":
            return httpx.Response(200, json=CAFETERIA_SNAPSHOT["days"][1])
        if channel == "patienten":
            return httpx.Response(200, json=PATIENTEN_SNAPSHOT["days"][1])
    match = re.fullmatch(r"^/api/v1/published/([^/]+)/days/(\d{4}-\d{2}-\d{2})$", path)
    if match:
        channel, date = match.groups()
        snapshot = PATIENTEN_SNAPSHOT if channel == "patienten" else CAFETERIA_SNAPSHOT
        for day in snapshot["days"]:
            if day["date"] == date:
                return httpx.Response(200, json=day)
    if path == "/api/v1/status":
        return httpx.Response(200, json=STATUS)
    if path == "/api/v1/weeks/cafeteria":
        return httpx.Response(200, json=WEEKS_CAFETERIA)
    if path == "/api/v1/weeks/cafeteria/2026-08-31/preview":
        return httpx.Response(200, json=WEEK_PREVIEW)
    if path == "/fhir/Composition/REV-CAF-KW36/$document":
        return httpx.Response(200, json=FHIR_DOCUMENT)
    if path == "/api/v1/openapi.json":
        return httpx.Response(200, json=OPENAPI)

    return httpx.Response(
        500,
        json={"error": "unhandled_mock_path", "detail": path},
    )


def invoke_tool(mcp_server: FastMCP, name: str, arguments: dict[str, object]) -> object:
    response = asyncio.run(mcp_server.call_tool(name, arguments))
    if isinstance(response, tuple) and len(response) == 2:
        result = response[1]
        if isinstance(result, dict):
            if "result" in result:
                return result["result"]
            if result:
                return result
    if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], list) and response[0]:
        first = response[0][0]
        if hasattr(first, "text"):
            return json.loads(first.text)
        if hasattr(first, "content"):
            return json.loads(first.content)
    if isinstance(response, list) and response:
        first = response[0]
        if hasattr(first, "text"):
            return json.loads(first.text)
        if hasattr(first, "content"):
            return json.loads(first.content)
        return response
    return response


def invoke_resource(mcp_server: FastMCP, uri: str) -> dict[str, object]:
    response = asyncio.run(mcp_server.read_resource(uri))
    if response:
        first = response[0]
        if hasattr(first, "text"):
            return json.loads(first.text)
        return json.loads(first.content)
    return {}


def test_list_tools_contains_exactly_seven_tools():
    with httpx.Client(
        base_url="https://dishboard.example",
        headers={"User-Agent": "dishboard-mcp/1.0", "Authorization": "Bearer test"},
        transport=httpx.MockTransport(mock_handler),
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        mcp_server = server.build_server(client)
        tools = asyncio.run(mcp_server.list_tools())
        tool_names = sorted(tool.name for tool in tools)
        assert tool_names == [
            "find_dishes",
            "get_day_menu",
            "get_fhir_document",
            "get_status",
            "get_week_menu",
            "get_week_preview",
            "list_weeks",
        ]


def test_all_tools_run_successfully_once():
    with httpx.Client(
        base_url="https://dishboard.example",
        headers={"User-Agent": "dishboard-mcp/1.0", "Authorization": "Bearer test"},
        transport=httpx.MockTransport(mock_handler),
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        mcp_server = server.build_server(client)
        assert isinstance(invoke_tool(mcp_server, "get_status", {}), dict)
        assert invoke_tool(mcp_server, "get_week_menu", {"channel": "cafeteria"})["channel"] == "cafeteria"
        assert invoke_tool(mcp_server, "get_day_menu", {"channel": "cafeteria", "date": "2026-09-01"})["date"] == "2026-09-01"
        results = invoke_tool(mcp_server, "find_dishes", {"query": "curry"})
        assert any(
            item["title"] == "Kichererbsen-Curry" and item["date"] == "2026-09-01" and "NUTS" in item["allergens"]
            for item in results
        )
        assert invoke_tool(mcp_server, "list_weeks", {"channel": "cafeteria"}) == WEEKS_CAFETERIA
        assert invoke_tool(mcp_server, "get_week_preview", {"channel": "cafeteria", "week_start": "2026-08-31"}) == WEEK_PREVIEW
        assert invoke_tool(mcp_server, "get_fhir_document", {"channel": "cafeteria"})["resourceType"] == "Bundle"


def test_get_week_menu_not_published_raises_tool_error():
    with httpx.Client(
        base_url="https://dishboard.example",
        headers={"User-Agent": "dishboard-mcp/1.0"},
        transport=httpx.MockTransport(mock_handler),
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        mcp_server = server.build_server(client)
        with pytest.raises(TOOL_ERROR, match="no_published_menu"):
            invoke_tool(mcp_server, "get_week_menu", {"channel": "ghost"})


def test_list_weeks_without_api_key_is_clear_error():
    with httpx.Client(
        base_url="https://dishboard.example",
        headers={"User-Agent": "dishboard-mcp/1.0"},
        transport=httpx.MockTransport(mock_handler),
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        mcp_server = server.build_server(client)
        with pytest.raises(TOOL_ERROR, match="DISHBOARD_API_KEY fehlt"):
            invoke_tool(mcp_server, "list_weeks", {"channel": "cafeteria"})


def test_read_resource_published_patienten_has_no_prices():
    with httpx.Client(
        base_url="https://dishboard.example",
        headers={"User-Agent": "dishboard-mcp/1.0", "Authorization": "Bearer test"},
        transport=httpx.MockTransport(mock_handler),
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        mcp_server = server.build_server(client)
        published = invoke_resource(mcp_server, "dishboard://published/patienten")
        assert published["channel"] == "patienten"
        for day in published["days"]:
            for service in day["services"]:
                for option in service["options"]:
                    assert "prices" not in option
