#!/usr/bin/env python3
"""Capture live screenshots from the running Dishboard Flask app."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, BrowserContext


@dataclass(frozen=True)
class ScreenshotDef:
    """Screenshot definition: name, route, dimensions, options."""

    name: str
    route: str
    width: int
    height: int
    requires_auth: bool = False
    requires_closed_day: bool = False


@dataclass
class CaptureResult:
    """Result of a single capture."""

    name: str
    url: str
    width: int
    height: int
    http_status: int
    sha256: str
    captured_at: str
    base_url: str
    console_errors: list[str]
    failed_requests: list[str]


# Inventory: screenshot definitions indexed by name
INVENTORY = {
    "login-1440x900.png": ScreenshotDef(
        "login-1440x900.png", "/auth/login", 1440, 900
    ),
    "auth-local-1440x900.png": ScreenshotDef(
        "auth-local-1440x900.png", "/auth/local", 1440, 900
    ),
    "website-cafeteria-heute-1440x1100.png": ScreenshotDef(
        "website-cafeteria-heute-1440x1100.png", "/cafeteria/heute/", 1440, 1100
    ),
    "website-cafeteria-woche-1440x1100.png": ScreenshotDef(
        "website-cafeteria-woche-1440x1100.png", "/cafeteria/wochenangebot/", 1440, 1100
    ),
    "website-patienten-heute-1440x1100.png": ScreenshotDef(
        "website-patienten-heute-1440x1100.png", "/patienten/heute/", 1440, 1100
    ),
    "website-patienten-woche-1440x1100.png": ScreenshotDef(
        "website-patienten-woche-1440x1100.png", "/patienten/wochenplan/", 1440, 1100
    ),
    "mobile-cafeteria-heute-390x844.png": ScreenshotDef(
        "mobile-cafeteria-heute-390x844.png", "/cafeteria/heute/", 390, 844
    ),
    "mobile-cafeteria-woche-390x844.png": ScreenshotDef(
        "mobile-cafeteria-woche-390x844.png", "/cafeteria/wochenangebot/", 390, 844
    ),
    "mobile-patienten-heute-390x844.png": ScreenshotDef(
        "mobile-patienten-heute-390x844.png", "/patienten/heute/", 390, 844
    ),
    "mobile-patienten-woche-390x844.png": ScreenshotDef(
        "mobile-patienten-woche-390x844.png", "/patienten/wochenplan/", 390, 844
    ),
    "admin-cafeteria-1440x900.png": ScreenshotDef(
        "admin-cafeteria-1440x900.png", "/admin/cafeteria", 1440, 900, requires_auth=True
    ),
    "admin-patienten-1440x900.png": ScreenshotDef(
        "admin-patienten-1440x900.png", "/admin/patienten", 1440, 900, requires_auth=True
    ),
    "signage-cafeteria-tag-1920x1080.png": ScreenshotDef(
        "signage-cafeteria-tag-1920x1080.png", "/signage/cafeteria/tag", 1920, 1080
    ),
    "signage-cafeteria-woche-1920x1080.png": ScreenshotDef(
        "signage-cafeteria-woche-1920x1080.png", "/signage/cafeteria/woche", 1920, 1080
    ),
    "signage-patienten-tag-1920x1080.png": ScreenshotDef(
        "signage-patienten-tag-1920x1080.png", "/signage/patienten/tag", 1920, 1080
    ),
    "signage-patienten-woche-1920x1080-vorschau.png": ScreenshotDef(
        "signage-patienten-woche-1920x1080-vorschau.png",
        "/signage/patienten/woche",
        1920,
        1080,
    ),
    "signage-patienten-woche-3840x2160.png": ScreenshotDef(
        "signage-patienten-woche-3840x2160.png", "/signage/patienten/woche", 3840, 2160
    ),
    "signage-cafeteria-geschlossen-1920x1080.png": ScreenshotDef(
        "signage-cafeteria-geschlossen-1920x1080.png",
        "/signage/cafeteria/tag",
        1920,
        1080,
        requires_closed_day=True,
    ),
}


def get_png_dimensions(png_data: bytes) -> tuple[int, int] | None:
    """Extract PNG width and height from PNG IHDR chunk (stdlib only)."""
    if len(png_data) < 24:
        return None
    # PNG signature: 89 50 4E 47 0D 0A 1A 0A
    if png_data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    # IHDR chunk: offset 8, 4 bytes length + "IHDR" + 4 bytes width + 4 bytes height
    try:
        width = struct.unpack(">I", png_data[16:20])[0]
        height = struct.unpack(">I", png_data[20:24])[0]
        return (width, height)
    except struct.error:
        return None


def read_password_file(path: str) -> str:
    """Read password from file (once, never print)."""
    return Path(path).read_text(encoding="utf-8").strip()


def _is_critical_request(url: str) -> bool:
    """Check if a request URL is for a critical resource (not favicon, etc)."""
    # Ignore non-critical assets
    ignore_patterns = [
        "/favicon.ico",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2", ".ttf", ".eot",
    ]
    for pattern in ignore_patterns:
        if pattern in url:
            return False
    return True


def perform_local_login(
    page: Page, base_url: str, username: str, password: str
) -> bool:
    """Perform local login: fetch /auth/local, extract CSRF, POST login."""
    try:
        # GET /auth/local to get the form with CSRF token
        response = page.goto(urljoin(base_url, "/auth/local"), wait_until="load")
        if not response or response.status not in (200, 204):
            return False

        # Extract CSRF token from the form
        csrf_input = page.query_selector('input[name="csrf_token"]')
        if not csrf_input:
            return False
        csrf_token = csrf_input.get_attribute("value")
        if not csrf_token:
            return False

        # Fill and submit the login form
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        
        # Use expect_navigation to handle redirect
        with page.expect_navigation():
            page.click('button[type="submit"]')
        
        # Wait for load to complete
        page.wait_for_load_state("load")
        
        # Check if we're now on an admin page (successful login redirects to /admin/cafeteria)
        current_url = page.url
        if "/admin/" not in current_url:
            return False
        
        return True
    except Exception:
        return False


def capture_screenshot(
    page: Page,
    base_url: str,
    def_: ScreenshotDef,
    username: str | None = None,
    password: str | None = None,
) -> tuple[bytes, int, list[str], list[str]] | None:
    """
    Capture a screenshot. Returns (png_data, http_status, console_errors, failed_requests) or None on failure.
    """
    console_errors = []
    failed_requests = []

    def on_console(msg):
        if msg.type == "error" and "Failed to load resource" not in msg.text:
                console_errors.append(msg.text)

    def on_response(resp):
        if resp.status >= 400 and _is_critical_request(resp.url):
            failed_requests.append(f"{resp.url} ({resp.status})")

    page.on("console", on_console)
    page.on("response", on_response)

    try:
        # For admin pages, perform login if needed
        if def_.requires_auth:
            if not username or not password:
                return None
            if not perform_local_login(page, base_url, username, password):
                return None
            # Now navigate to the specific admin page if not already there
            url = urljoin(base_url, def_.route)
            response = page.goto(url, wait_until="load")
            http_status = response.status if response else 500
        else:
            # Navigate to the route
            url = urljoin(base_url, def_.route)
            response = page.goto(url, wait_until="load")
            http_status = response.status if response else 500

        if http_status not in (200, 204):
            return None

        # Fail if there are console errors or failed requests
        if console_errors or failed_requests:
            return None

        body_text = page.text_content("body") or ""

        # Special validation for login-1440x900.png: final URL must end with /auth/local
        if def_.name == "login-1440x900.png":
            if not page.url.endswith("/auth/local"):
                return None

        # Check for viewport overflow on signage pages
        if "signage" in def_.name:
            overflow = page.evaluate(
                """() => {
                const el = document.scrollingElement || document.documentElement;
                return {
                    hasHorizontal: el.scrollWidth > window.innerWidth,
                    hasVertical: el.scrollHeight > window.innerHeight
                };
            }"""
            )
            if overflow["hasHorizontal"] or overflow["hasVertical"]:
                return None

            # Check for forbidden elements on signage
            if page.query_selector("a[href], nav, form"):
                return None

            # Check for closed-day requirement
            if def_.requires_closed_day:
                if "geschlossen" not in body_text.lower():
                    return None

        # Check for patient data privacy tokens on patient pages
        if "patienten" in def_.name or "patient" in def_.name:
            forbidden_tokens = ["CHF", "Intern", "Extern", "0.00"]
            for token in forbidden_tokens:
                if re.search(r"\b" + re.escape(token) + r"\b", body_text):
                    return None

        # Check for horizontal overflow on all pages
        overflow = page.evaluate(
            """() => {
            const el = document.scrollingElement || document.documentElement;
            return el.scrollWidth > window.innerWidth;
        }"""
        )
        if overflow:
            return None

        # Capture screenshot
        png_data = page.screenshot(full_page=False)
        return (png_data, http_status, console_errors, failed_requests)

    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture live screenshots from the running Dishboard Flask app."
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of the Flask app (e.g., http://127.0.0.1:8789)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for screenshots (default: <repo_root>/design/screenshots/live)",
    )
    parser.add_argument(
        "--select",
        nargs="+",
        help="Subset of screenshot names to capture (default: all)",
    )
    parser.add_argument(
        "--username",
        help="Username for admin captures",
    )
    parser.add_argument(
        "--password-file",
        help="Path to file containing the password for admin captures",
    )
    parser.add_argument(
        "--browser-path",
        type=Path,
        help="Optional path to Chromium/Chrome browser",
    )
    parser.add_argument(
        "--closed-today",
        action="store_true",
        help="Mark that the server date is a closed cafeteria day",
    )

    args = parser.parse_args()

    # Determine output directory
    if args.output:
        output = args.output.resolve()
    else:
        repo_root = Path(__file__).resolve().parents[1]
        output = repo_root / "design" / "screenshots" / "live"

    output.mkdir(parents=True, exist_ok=True)

    # Determine which captures to run
    selected_names = set(args.select or INVENTORY.keys())
    to_capture = {k: v for k, v in INVENTORY.items() if k in selected_names}

    if not to_capture:
        print("Error: No screenshots selected.", flush=True)
        return 1

    # Check if admin captures are requested
    admin_needed = any(def_.requires_auth for def_ in to_capture.values())
    if admin_needed and not (args.username and args.password_file):
        print("Error: Admin capture requested but --username and --password-file not provided.", flush=True)
        return 1

    # Read password if needed
    password = None
    if args.password_file:
        try:
            password = read_password_file(args.password_file)
        except Exception as e:
            print(f"Error reading password file: {e}", flush=True)
            return 1

    # Check closed-day requirement
    if any(def_.requires_closed_day for def_ in to_capture.values()):
        if not args.closed_today:
            print("Error: Closed-day capture requested but --closed-today not set.", flush=True)
            return 1

    # Set up Playwright
    browser_path = str(args.browser_path.resolve()) if args.browser_path else (
        shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    )
    launch_options = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"],
    }
    if browser_path:
        launch_options["executable_path"] = browser_path

    results = []
    failed = False

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        try:
            for name, def_ in to_capture.items():
                context: BrowserContext = browser.new_context(
                    viewport={"width": def_.width, "height": def_.height},
                    device_scale_factor=1,
                    locale="de-CH",
                    color_scheme="light",
                )
                page = context.new_page()

                try:
                    # Disable animations
                    page.emulate_media(reduced_motion="reduce")

                    result = capture_screenshot(
                        page,
                        args.base_url,
                        def_,
                        username=args.username,
                        password=password,
                    )

                    if result is None:
                        print(f"{name}: FAILED", flush=True)
                        failed = True
                        context.close()
                        continue

                    png_data, http_status, console_errors, failed_requests = result

                    # Validate PNG dimensions
                    dims = get_png_dimensions(png_data)
                    if dims != (def_.width, def_.height):
                        print(f"{name}: FAILED (dimension mismatch: {dims} != {def_.width}x{def_.height})", flush=True)
                        failed = True
                        context.close()
                        continue

                    # Write PNG file
                    png_path = output / name
                    png_path.write_bytes(png_data)

                    # Compute SHA256
                    sha256_hash = hashlib.sha256(png_data).hexdigest()

                    # Record result
                    result_entry = CaptureResult(
                        name=name,
                        url=urljoin(args.base_url, def_.route),
                        width=def_.width,
                        height=def_.height,
                        http_status=http_status,
                        sha256=sha256_hash,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        base_url=args.base_url,
                        console_errors=console_errors,
                        failed_requests=failed_requests,
                    )
                    results.append(result_entry)
                    print(f"{name}: OK ({def_.width}x{def_.height})", flush=True)

                except Exception as e:
                    print(f"{name}: ERROR ({e})", flush=True)
                    failed = True
                finally:
                    context.close()

        finally:
            browser.close()

    # Write INDEX.json as a sorted list
    try:
        index_path = output / "INDEX.json"
        existing_list = []
        if index_path.exists():
            content = json.loads(index_path.read_text(encoding="utf-8"))
            # Handle both old dict format and new list format
            if isinstance(content, dict):
                existing_list = list(content.values())
            else:
                existing_list = content

        # Create a dict for easier merging
        existing_dict = {item["name"]: item for item in existing_list}

        # Update with new results
        for result in results:
            existing_dict[result.name] = asdict(result)

        # Convert back to sorted list by name
        final_list = sorted(existing_dict.values(), key=lambda x: x["name"])

        index_path.write_text(
            json.dumps(final_list, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"Error writing INDEX.json: {e}", flush=True)
        return 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
