from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import threading
import time
from hashlib import sha256
from pathlib import Path
from typing import Iterator

import pytest
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
REDIS_URL = os.getenv('TEST_REDIS_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
LOCAL_ACTOR_ID = 'capture.admin@example.invalid'

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason='TEST_DATABASE_URL und TEST_REDIS_URL für Live-Server-Tests fehlen.',
)

if DATABASE_URL and REDIS_URL:
    from cafeteria import create_app
    from cafeteria.auth import issuer as auth_issuer
    from cafeteria.db import init_database, upsert_entra_user


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


def _find_free_port() -> int:
    """Find a free TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _cleanup_database(database_url: str) -> None:
    """Drop and recreate the cafeteria schema."""
    owner_engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        with owner_engine.begin() as connection:
            # Skip grant when schema might not exist
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
    finally:
        owner_engine.dispose()


@pytest.fixture
def live_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Start the Flask app in a background thread on a free port."""
    assert DATABASE_URL is not None
    assert REDIS_URL is not None

    # Clean up the database
    _cleanup_database(DATABASE_URL)

    # Initialize the database
    init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        demo_seed_path=str(ROOT / 'database' / 'seed_demo.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
        seed_demo=True,
    )

    # Set up environment
    app_url = _role_database_url('cafeteria_app', APP_PASSWORD)
    monkeypatch.setenv('DATABASE_URL', app_url)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('SESSION_REDIS_URL', REDIS_URL)
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test-capture-secret')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SEED_DEMO', 'true')
    monkeypatch.setenv('DEMO_TODAY', '2026-09-01')

    # Create the Flask app
    application = create_app()
    application.config.update(TESTING=False)

    # Provision an admin user via Entra first
    issuer_engine = application.extensions['cafeteria_auth_issuer_db']
    upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000711',
            'oid': '00000000-0000-0000-0000-000000000722',
            'sub': 'capture-admin-actor',
            'name': 'Capture Admin',
            'preferred_username': LOCAL_ACTOR_ID,
        },
        ['Cafeteria.Admin'],
    )

    # Now provision a local user
    auth_issuer.provision_local_user(
        issuer_engine,
        actor_identifier=LOCAL_ACTOR_ID,
        username='capture.admin',
        display_name='Capture Admin',
        password='MysteryKeeper2026!@Xyz',
        roles=['Cafeteria.Admin'],
    )

    # Start the server in a background thread
    port = _find_free_port()
    base_url = f'http://127.0.0.1:{port}'

    server = make_server('127.0.0.1', port, application, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Wait for the server to be ready
    time.sleep(0.5)

    try:
        yield base_url
    finally:
        server.shutdown()
        application.extensions['cafeteria_db'].dispose()
        issuer_engine.dispose()
        _cleanup_database(DATABASE_URL)
        redis_client = Redis.from_url(REDIS_URL)
        redis_client.flushdb()
        redis_client.close()


@pytest.fixture
def live_server_closed_day(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Start the Flask app with a closed day (Sunday 2026-09-06)."""
    assert DATABASE_URL is not None
    assert REDIS_URL is not None

    # Clean up the database
    _cleanup_database(DATABASE_URL)

    # Initialize the database
    init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        demo_seed_path=str(ROOT / 'database' / 'seed_demo.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
        seed_demo=True,
    )

    # Set up environment
    app_url = _role_database_url('cafeteria_app', APP_PASSWORD)
    monkeypatch.setenv('DATABASE_URL', app_url)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('SESSION_REDIS_URL', REDIS_URL)
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test-capture-secret-closed')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SEED_DEMO', 'true')
    monkeypatch.setenv('DEMO_TODAY', '2026-09-06')

    # Create the Flask app
    application = create_app()
    application.config.update(TESTING=False)

    # Start the server in a background thread
    port = _find_free_port()
    base_url = f'http://127.0.0.1:{port}'

    server = make_server('127.0.0.1', port, application, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Wait for the server to be ready
    time.sleep(0.5)

    try:
        yield base_url
    finally:
        server.shutdown()
        application.extensions['cafeteria_db'].dispose()
        issuer_engine = application.extensions['cafeteria_auth_issuer_db']
        issuer_engine.dispose()
        _cleanup_database(DATABASE_URL)
        redis_client = Redis.from_url(REDIS_URL)
        redis_client.flushdb()
        redis_client.close()


def _get_png_dimensions(png_data: bytes) -> tuple[int, int] | None:
    """Extract PNG width and height from PNG IHDR chunk."""
    if len(png_data) < 24:
        return None
    # PNG signature
    if png_data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        width = struct.unpack(">I", png_data[16:20])[0]
        height = struct.unpack(">I", png_data[20:24])[0]
        return (width, height)
    except struct.error:
        return None


def test_capture_live_screenshots(live_server: str, tmp_path: Path) -> None:
    """Test capturing a subset of screenshots from a live server."""
    # Write password to a temp file
    password_file = tmp_path / 'password.txt'
    password_file.write_text('MysteryKeeper2026!@Xyz', encoding='utf-8')

    # Capture a subset
    captures = [
        'signage-cafeteria-tag-1920x1080.png',
        'mobile-patienten-heute-390x844.png',
        'website-cafeteria-woche-1440x1100.png',
        'admin-cafeteria-1440x900.png',
        'signage-patienten-woche-3840x2160.png',
    ]

    output_dir = tmp_path / 'screenshots'

    tool_path = ROOT / 'tools' / 'capture_live_screenshots.py'
    result = subprocess.run(
        [
            '/tmp/dishboard-shared-venv/bin/python',
            str(tool_path),
            '--base-url', live_server,
            '--output', str(output_dir),
            '--select', *captures,
            '--username', 'capture.admin',
            '--password-file', str(password_file),
        ],
        capture_output=True,
        text=True,
    )

    # Should succeed with exit code 0
    assert result.returncode == 0, f"Tool failed: {result.stdout}\n{result.stderr}"

    # Verify INDEX.json exists and has correct entries
    index_path = output_dir / 'INDEX.json'
    assert index_path.exists(), "INDEX.json not created"

    index_data = json.loads(index_path.read_text(encoding='utf-8'))

    for capture_name in captures:
        assert capture_name in index_data, f"{capture_name} not in INDEX.json"
        entry = index_data[capture_name]

        # Verify PNG file exists
        png_path = output_dir / capture_name
        assert png_path.exists(), f"{capture_name} not created"

        # Verify PNG dimensions match
        png_data = png_path.read_bytes()
        dims = _get_png_dimensions(png_data)
        expected_dims = (entry['width'], entry['height'])
        assert dims == expected_dims, f"PNG dimensions {dims} != {expected_dims}"

        # Verify SHA256
        computed_sha = sha256(png_data).hexdigest()
        assert computed_sha == entry['sha256'], f"SHA256 mismatch for {capture_name}"

        # Verify HTTP status is 200
        assert entry['http_status'] == 200, f"HTTP status {entry['http_status']} != 200 for {capture_name}"


def test_capture_with_wrong_password_fails(live_server: str, tmp_path: Path) -> None:
    """Test that wrong password causes admin capture to fail."""
    # Write wrong password
    password_file = tmp_path / 'password.txt'
    password_file.write_text('Wrong-Password-2026!', encoding='utf-8')

    output_dir = tmp_path / 'screenshots'

    tool_path = ROOT / 'tools' / 'capture_live_screenshots.py'
    result = subprocess.run(
        [
            '/tmp/dishboard-shared-venv/bin/python',
            str(tool_path),
            '--base-url', live_server,
            '--output', str(output_dir),
            '--select', 'admin-cafeteria-1440x900.png',
            '--username', 'capture.admin',
            '--password-file', str(password_file),
        ],
        capture_output=True,
        text=True,
    )

    # Should fail with exit code 1
    assert result.returncode != 0, "Tool should fail with wrong password"

    # admin-cafeteria PNG should NOT exist
    admin_png = output_dir / 'admin-cafeteria-1440x900.png'
    assert not admin_png.exists(), "PNG created despite failed login"


def test_capture_closed_day_fails_without_flag(live_server: str, tmp_path: Path) -> None:
    """Test that closed-day capture fails without --closed-today flag."""
    output_dir = tmp_path / 'screenshots'

    tool_path = ROOT / 'tools' / 'capture_live_screenshots.py'
    result = subprocess.run(
        [
            '/tmp/dishboard-shared-venv/bin/python',
            str(tool_path),
            '--base-url', live_server,
            '--output', str(output_dir),
            '--select', 'signage-cafeteria-geschlossen-1920x1080.png',
        ],
        capture_output=True,
        text=True,
    )

    # Should fail because --closed-today not provided
    assert result.returncode != 0, "Should fail without --closed-today"


def test_capture_closed_day_succeeds_on_closed_server(
    live_server_closed_day: str, tmp_path: Path
) -> None:
    """Test that closed-day capture succeeds on a server with a closed day."""
    output_dir = tmp_path / 'screenshots'

    tool_path = ROOT / 'tools' / 'capture_live_screenshots.py'
    result = subprocess.run(
        [
            '/tmp/dishboard-shared-venv/bin/python',
            str(tool_path),
            '--base-url', live_server_closed_day,
            '--output', str(output_dir),
            '--select', 'signage-cafeteria-geschlossen-1920x1080.png',
            '--closed-today',
        ],
        capture_output=True,
        text=True,
    )

    # Should succeed
    assert result.returncode == 0, f"Should succeed with --closed-today on closed day: {result.stderr}"

    # Verify PNG was created
    png_path = output_dir / 'signage-cafeteria-geschlossen-1920x1080.png'
    assert png_path.exists(), "PNG not created"
