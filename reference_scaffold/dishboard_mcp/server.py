from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from os import environ

import httpx
from mcp.server.fastmcp import FastMCP

from . import __version__

try:
    from mcp.server.fastmcp.exceptions import ToolError
except ImportError:  # pragma: no cover - Fallback bei sehr alten Versionen
    ToolError = None


def _tool_error(error: str, detail: str | None = None) -> Exception:
    payload = {"error": error, "detail": detail}
    message = json.dumps(payload, ensure_ascii=False)
    if ToolError is None:
        return ValueError(message)
    return ToolError(message)


def _json_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        parsed = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    if response.is_success:
        raise _tool_error("invalid_response", "Dishboard-Antwort muss ein JSON-Objekt sein")
    return {}


def _require_api_key(headers: Mapping[str, str]) -> None:
    if "authorization" not in headers and "Authorization" not in headers:
        raise _tool_error("authorization", "DISHBOARD_API_KEY fehlt")


def _require_json_response(response: httpx.Response) -> dict[str, Any]:
    payload = _json_payload(response)
    if response.status_code == 404 and payload.get("error") == "no_published_menu":
        raise _tool_error("no_published_menu", payload.get("detail"))
    if not response.is_success:
        raise _tool_error(payload.get("error", f"HTTP {response.status_code}"), payload.get("detail", response.text))
    return payload


def _fetch_json(client: httpx.Client, path: str) -> dict[str, Any]:
    response = client.get(path)
    return _require_json_response(response)


def _fetch_json_optional(client: httpx.Client, path: str) -> dict[str, Any] | None:
    response = client.get(path)
    payload = _json_payload(response)
    if response.status_code == 404 and payload.get("error") == "no_published_menu":
        return None
    if not response.is_success:
        raise _tool_error(payload.get("error", f"HTTP {response.status_code}"), payload.get("detail", response.text))
    return payload


def _contains_casefold(haystack: Any, needle: str) -> bool:
    if haystack is None:
        return False
    return needle in str(haystack).casefold()


def build_server(client: httpx.Client) -> FastMCP:
    """
    Baue FastMCP-Server mit Dishboard-Werkzeugen und -Ressourcen.
    Parameter: client (httpx.Client).
    """

    server = FastMCP(f"dishboard-mcp/{__version__}")

    @server.tool()
    def get_status() -> dict[str, Any]:
        """Liefere den Serverstatus. Parameter: keine."""
        return _fetch_json(client, "/api/v1/status")

    @server.tool()
    def get_week_menu(channel: str) -> dict[str, Any]:
        """Liefere Publikation pro Kanal. Parameter: channel."""
        return _fetch_json(client, f"/api/v1/published/{channel}")

    @server.tool()
    def get_day_menu(channel: str, date: str | None = None) -> dict[str, Any]:
        """Liefere Tagesmenü für Kanal und optionales Datum. Parameter: channel, date."""
        if date is None:
            return _fetch_json(client, f"/api/v1/published/{channel}/today")
        return _fetch_json(client, f"/api/v1/published/{channel}/days/{date}")

    @server.tool()
    def find_dishes(query: str, channel: str | None = None) -> list[dict[str, Any]]:
        """Finde Gerichte mit Suchbegriff. Parameter: query, channel."""
        needle = query.casefold()
        channels = (channel,) if channel else ("cafeteria", "patienten")
        results: list[dict[str, Any]] = []

        for current_channel in channels:
            snapshot = _fetch_json_optional(client, f"/api/v1/published/{current_channel}")
            if snapshot is None:
                continue

            for day in snapshot.get("days", []):
                date = day.get("date")
                weekday = day.get("weekday")
                for service in day.get("services", []):
                    meal_code = service.get("meal_code")
                    for option in service.get("options", []):
                        title = option.get("title", "")
                        description = option.get("description", "")
                        components = option.get("components", [])
                        allergens = option.get("allergens", [])
                        labels = option.get("labels", [])

                        search_fields = [title, description]
                        search_fields.extend(components)
                        search_fields.extend(allergen.get("name", "") for allergen in allergens)
                        search_fields.extend(label.get("name", "") for label in labels)
                        if any(_contains_casefold(field, needle) for field in search_fields):
                            results.append(
                                {
                                    "channel": current_channel,
                                    "date": date,
                                    "weekday": weekday,
                                    "meal_code": meal_code,
                                    "type_code": option.get("type_code"),
                                    "title": title,
                                    "allergens": [item.get("code") for item in allergens if item.get("code")],
                                    "labels": [item.get("code") for item in labels if item.get("code")],
                                }
                            )

        return results

    @server.tool()
    def list_weeks(channel: str) -> dict[str, Any]:
        """Lese Wochenübersicht im Vorschaumodus. Parameter: channel."""
        _require_api_key(dict(client.headers))
        return _fetch_json(client, f"/api/v1/weeks/{channel}")

    @server.tool()
    def get_week_preview(channel: str, week_start: str) -> dict[str, Any]:
        """Lade Vorschau einer Woche. Parameter: channel, week_start."""
        _require_api_key(dict(client.headers))
        return _fetch_json(client, f"/api/v1/weeks/{channel}/{week_start}/preview")

    @server.tool()
    def get_fhir_document(channel: str) -> dict[str, Any]:
        """Lade FHIR-Dokument einer Revision. Parameter: channel."""
        status = _fetch_json(client, "/api/v1/status")
        revision = None
        for item in status.get("channels", []):
            if item.get("channel") == channel:
                revision = item.get("revision_id")
                break
        if not revision:
            raise _tool_error("no_published_menu", f"Keine Revision für Kanal {channel}")
        return _fetch_json(client, f"/fhir/Composition/{revision}/$document")

    @server.resource("dishboard://published/{channel}")
    def published_resource(channel: str) -> dict[str, Any] | None:
        """Lese das veröffentlichte Snapshot als Resource. Parameter: channel."""
        return _fetch_json_optional(client, f"/api/v1/published/{channel}")

    @server.resource("dishboard://openapi")
    def openapi_resource() -> dict[str, Any]:
        """Lese die OpenAPI-Spezifikation als Resource. Parameter: keine."""
        return _fetch_json(client, "/api/v1/openapi.json")

    return server


def main() -> None:
    """Starte den MCP-Server über stdio. Parameter: keine."""
    base_url = environ.get("DISHBOARD_BASE_URL", "http://localhost:8080")
    api_key = environ.get("DISHBOARD_API_KEY", "").strip()
    timeout_seconds = float(environ.get("DISHBOARD_TIMEOUT_SECONDS", "10"))
    headers = {"User-Agent": "dishboard-mcp/1.0"}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    client = httpx.Client(
        base_url=base_url,
        headers=headers,
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    server = build_server(client)
    server.run()


__all__ = ["build_server", "main"]
