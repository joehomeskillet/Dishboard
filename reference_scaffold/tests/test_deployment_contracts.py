from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
PRODUCTION_HOST = "dishboard.joelduss.xyz"


def load_compose(name: str) -> dict:
    return yaml.safe_load((DEPLOYMENT / name).read_text(encoding="utf-8"))


def run_entrypoint(
    tmp_path: Path,
    secret_text: str = "not-a-placeholder-secret\n",
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    secret_file = tmp_path / "entra_client_secret.txt"
    secret_file.write_text(secret_text, encoding="utf-8")
    environment = os.environ | {
        "APP_ENV": "production",
        "APP_PUBLIC_BASE_URL": f"https://{PRODUCTION_HOST}",
        "CAFETERIA_DOMAIN": PRODUCTION_HOST,
        "DEMO_MODE": "false",
        "SEED_DEMO": "false",
        "DEMO_TODAY": "",
        "ENTRA_ENABLED": "true",
        "ENTRA_TENANT_ID": "11111111-1111-1111-1111-111111111111",
        "ENTRA_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        "ENTRA_CLIENT_SECRET_FILE": str(secret_file),
    }
    environment.update(overrides)
    return subprocess.run(
        ["/bin/sh", str(DEPLOYMENT / "entrypoint.sh"), "/bin/true"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_deployment_defaults_to_dishboard_and_persists_last_good() -> None:
    """A restart must retain player fallback state at the public deployment host."""
    environment_example = (DEPLOYMENT / ".env.example").read_text(encoding="utf-8")
    compose = load_compose("docker-compose.yml")
    caddy_overlay = load_compose("docker-compose.caddy.yml")

    assert f"CAFETERIA_DOMAIN={PRODUCTION_HOST}" in environment_example
    assert f"APP_PUBLIC_BASE_URL=https://{PRODUCTION_HOST}" in environment_example
    assert caddy_overlay["services"]["caddy"]["environment"]["CAFETERIA_DOMAIN"] == (
        f"${{CAFETERIA_DOMAIN:-{PRODUCTION_HOST}}}"
    )
    assert compose["services"]["app"]["environment"]["LAST_GOOD_DIR"] == "/var/lib/cafeteria/last-good"
    assert "last_good_data:/var/lib/cafeteria" in compose["services"]["app"]["volumes"]
    assert "last_good_data" in compose["volumes"]


def test_production_entrypoint_rejects_demo_and_placeholder_entra_values(tmp_path: Path) -> None:
    """A production process must not start with demo or placeholder Entra settings."""
    demo_result = run_entrypoint(tmp_path, DEMO_MODE="true")
    placeholder_result = run_entrypoint(
        tmp_path,
        ENTRA_CLIENT_ID="00000000-0000-0000-0000-000000000000",
    )

    assert demo_result.returncode != 0
    assert "DEMO_MODE" in demo_result.stderr
    assert placeholder_result.returncode != 0
    assert "ENTRA_CLIENT_ID" in placeholder_result.stderr


def test_production_entrypoint_rejects_placeholder_entra_secret(tmp_path: Path) -> None:
    """The bootstrap placeholder may not authenticate a production Entra deployment."""
    result = run_entrypoint(
        tmp_path,
        secret_text="REPLACE_WITH_ENTRA_CLIENT_SECRET_FOR_PRODUCTION\n",
    )

    assert result.returncode != 0
    assert "ENTRA_CLIENT_SECRET_FILE" in result.stderr


def test_entra_callbacks_and_healthchecks_do_not_expose_secret_arguments() -> None:
    """Entra and health checks keep the deployed callback contract without CLI secrets."""
    redirects = (ROOT / "entra" / "redirect-uris.txt").read_text(encoding="utf-8")
    compose_text = (DEPLOYMENT / "docker-compose.yml").read_text(encoding="utf-8")

    assert f"https://{PRODUCTION_HOST}/auth/callback" in redirects
    assert f"https://{PRODUCTION_HOST}/auth/frontchannel-logout" in redirects
    assert "redis-cli -a" not in compose_text
    assert "PGPASSWORD=" not in compose_text
    assert "--requirepass" not in compose_text
    assert "--aclfile /tmp/redis-users.acl" in compose_text


def test_bootstrap_generates_only_technical_secrets(tmp_path: Path) -> None:
    """Bootstrap is host-runnable and creates no Entra credential beyond its disabled marker."""
    staged_deployment = tmp_path / "deployment"
    shutil.copytree(DEPLOYMENT, staged_deployment)

    result = subprocess.run(
        ["/bin/sh", str(staged_deployment / "bootstrap.sh")],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    for name in (
        "postgres_owner_password.txt",
        "postgres_app_password.txt",
        "postgres_backup_password.txt",
        "flask_secret_key.txt",
        "redis_password.txt",
    ):
        secret_file = staged_deployment / "secrets" / name
        assert secret_file.read_text(encoding="utf-8").strip()
        assert secret_file.stat().st_mode & 0o777 == 0o600
    assert (staged_deployment / "secrets" / "entra_client_secret.txt").read_text(encoding="utf-8").strip() == (
        "REPLACE_WITH_ENTRA_CLIENT_SECRET_FOR_PRODUCTION"
    )
