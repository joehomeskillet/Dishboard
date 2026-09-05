#!/usr/bin/env python3
"""Generate one reviewed-menu candidate with Google through OpenRouter.

Uses only the standard library. Authentication follows the installed or-chat
client: an injected key, or its existing protected key file. Values are never
printed. The fixed model/provider cannot fall back to another paid service.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

MODEL = "google/gemini-3.1-flash-image"
ENDPOINT = "https://openrouter.ai/api/v1/images"
ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGES = 24
BUDGET = Decimal("3.00")
RESERVE = Decimal("0.30")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward an authorization header to a redirected endpoint."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def credential() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        try:
            # Same trusted runtime credential source as /usr/local/bin/or-chat.
            key = Path("/root/.openrouter-key").read_text().strip()
        except OSError:
            raise RuntimeError("OpenRouter runtime credential unavailable") from None
    if not key or "\n" in key or "\r" in key:
        raise RuntimeError("OpenRouter runtime credential invalid")
    return key


def dimensions(data: bytes) -> tuple[str, int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return ".png", width, height
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 255:
                break
            marker = data[offset + 1]
            length = int.from_bytes(data[offset + 2:offset + 4], "big")
            if length < 2:
                break
            if marker in (192, 193, 194):
                height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
                return ".jpg", width, height
            offset += length + 2
    raise RuntimeError("Image output is not a supported PNG or JPEG")


def save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def generate(menu_id: int) -> dict[str, Any]:
    directory = ROOT / "design/menu-images"
    manifest = json.loads((directory / "manifest.json").read_text())
    entries = [entry for entry in manifest["images"]
               if entry["source_menu_ids"][0] == menu_id]
    if len(entries) != 1 or entries[0]["status"] == "ready":
        raise RuntimeError("Menu must be a pending or revision composition ID")
    entry = entries[0]
    reference = ROOT / manifest["reference"]["file"]
    reference_bytes = reference.read_bytes()
    reference_hash = hashlib.sha256(reference_bytes).hexdigest()
    if reference_hash != manifest["reference"]["sha256"]:
        raise RuntimeError("Canonical reference hash changed")
    key = credential()
    output = directory / "openrouter"
    output.mkdir(exist_ok=True)
    with (output / ".generation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipts = [json.loads(path.read_text()) for path in output.glob("*.json")]
        if len(receipts) >= MAX_IMAGES:
            raise RuntimeError("Maximum 24 image requests reached")
        if any(row["status"] != "generated" for row in receipts):
            raise RuntimeError("Earlier image request needs cost/error reconciliation")
        spent = sum((Decimal(str(row["cost_usd"])) for row in receipts), Decimal(0))
        if spent + RESERVE > BUDGET:
            raise RuntimeError("USD 3 budget guard reached")
        receipt_path = output / f"menu-{menu_id:03}.json"
        if receipt_path.exists():
            raise RuntimeError("This menu already has an OpenRouter request receipt")
        prompt = (
            "Edit the supplied canonical empty-plate photograph. Preserve exactly "
            "its warm off-white matte background, identical plain white round deep "
            "ceramic plate, centered position and scale, exact 90-degree overhead "
            "camera and soft upper-left daylight. Change only food inside the plate. "
            f"Ordinary Swiss cafeteria portion: {entry['title']}. "
            f"All required side components: {', '.join(entry['components'])}. "
            "Show the named main dish and every side component clearly. No invented "
            "extra side dish. No garnish, decorative herb leaves, herb sprigs or green "
            "flecks unless herbs are explicitly part of the menu title. No utensils, "
            "hands, text, logos, napkins, extra containers or food on the tabletop. "
            "Vegetarian dishes must visibly contain no meat or fish. Natural food "
            "texture and modest portions, no icons or luxury styling. Output only "
            "a pure photograph: no writing anywhere, including the plate rim."
        )
        if "Hausbrot" in entry["components"]:
            prompt += " Place the named bread on the upper rim of this same deep plate."
        if any(name in entry["components"] for name in ("Apfelmus", "Zwetschgenkompott")):
            prompt += " Serve the named fruit puree or compote inside this same plate."
        if menu_id == 108:
            prompt += (
                " Exactly three sections: chickpea stew, potato wedges, mixed market "
                "vegetables. Absolutely no bread, fruit, fruit puree, compote, herbs, "
                "letters, captions or markings. The entire white rim must stay empty."
            )
        payload = {
            "model": MODEL, "prompt": prompt, "n": 1,
            "resolution": "1K", "aspect_ratio": "4:3",
            "input_references": [{"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," +
                base64.b64encode(reference_bytes).decode("ascii")}}],
            "provider": {"only": ["google-ai-studio"], "allow_fallbacks": False},
        }
        receipt: dict[str, Any] = {
            "menu_id": menu_id, "model": MODEL, "provider": "google-ai-studio",
            "status": "started", "reserved_usd": str(RESERVE),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reference_sha256": reference_hash, "prompt": prompt,
            "resolution": "1K", "aspect_ratio": "4:3",
        }
        save_receipt(receipt_path, receipt)
        request = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "X-Title": "Dishboard menu images"},
        )
        try:
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(request, timeout=180) as response:
                raw = response.read(25 * 1024 * 1024 + 1)
            if len(raw) > 25 * 1024 * 1024:
                raise RuntimeError("Image response exceeds size limit")
            result = json.loads(raw)
            usage = result.get("usage", {})
            cost = Decimal(str(usage.get("cost")))
            if not cost.is_finite() or cost < 0:
                raise RuntimeError("Image response contains invalid cost")
            receipt["cost_usd"] = str(cost)
            images = result.get("data", [])
            if len(images) != 1:
                raise RuntimeError("Expected exactly one image output")
            data = base64.b64decode(images[0]["b64_json"], validate=True)
            suffix, width, height = dimensions(data)
            image_path = output / f"menu-{menu_id:03}-google-or{suffix}"
            with image_path.open("xb") as image_file:
                image_file.write(data)
            receipt.update(
                status="generated", file=str(image_path.relative_to(ROOT)),
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                width=width, height=height, total_cost_usd=str(spent + cost),
                exceeds_budget=spent + cost > BUDGET,
            )
            save_receipt(receipt_path, receipt)
            return receipt
        except urllib.error.HTTPError as exc:
            receipt.update(status="failed", http_status=exc.code)
            save_receipt(receipt_path, receipt)
            raise RuntimeError(f"OpenRouter HTTP {exc.code}; no retry or fallback") from None
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, ArithmeticError) as exc:
            receipt.update(status="unknown", error_class=type(exc).__name__)
            save_receipt(receipt_path, receipt)
            raise RuntimeError("Generation incomplete; inspect redacted receipt before retry") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menu-id", type=int, required=True)
    args = parser.parse_args()
    try:
        receipt = generate(args.menu_id)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in receipt.items() if key != "prompt"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
