from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
PRODUCTION_HOST = "dishboard.joelduss.xyz"
PRODUCTION_ORIGIN = f"https://{PRODUCTION_HOST}"
PINNED_APP_IMAGE = "registry.example.invalid/dishboard@sha256:" + ("1" * 64)


def load_compose(name: str) -> dict:
    return yaml.safe_load((DEPLOYMENT / name).read_text(encoding="utf-8"))


def load_environment_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (DEPLOYMENT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def run_entrypoint(
    tmp_path: Path,
    secret_text: str = "not-a-placeholder-secret\n",
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    secret_file = tmp_path / "entra_client_secret.txt"
    secret_file.write_text(secret_text, encoding="utf-8")
    environment = os.environ | {
        "APP_ENV": "production",
        "APP_PUBLIC_BASE_URL": PRODUCTION_ORIGIN,
        "APP_IMAGE": PINNED_APP_IMAGE,
        "CAFETERIA_DOMAIN": PRODUCTION_HOST,
        "DEMO_MODE": "false",
        "SEED_DEMO": "false",
        "DEMO_TODAY": "",
        "SESSION_COOKIE_SECURE": "true",
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


def test_default_public_host_environment_is_production_safe() -> None:
    """The shipped dishboard host defaults must never enable development or demo data."""
    environment = load_environment_example()

    assert environment["APP_PUBLIC_BASE_URL"] == f"https://{PRODUCTION_HOST}"
    assert environment["CAFETERIA_DOMAIN"] == PRODUCTION_HOST
    assert environment["APP_ENV"] == "production"
    assert environment["DEMO_MODE"] == "false"
    assert environment["SEED_DEMO"] == "false"
    assert environment["DEMO_TODAY"] == ""
    assert environment["SESSION_COOKIE_SECURE"] == "true"
    assert environment["APP_IMAGE"].endswith("@sha256:REPLACE_WITH_IMAGE_DIGEST")


def test_compose_requires_an_explicit_app_image_digest() -> None:
    """Production must not silently build or deploy a mutable local/latest image."""
    compose = load_compose("docker-compose.yml")
    app_image = compose["x-app-image"]["image"]

    assert app_image == "${APP_IMAGE:?Set APP_IMAGE to an immutable image digest}"
    assert "IMAGE_TAG" not in app_image
    assert compose["services"]["app"]["environment"]["APP_IMAGE"] == "${APP_IMAGE}"


def test_migrate_service_uses_only_database_secrets_and_safe_runtime_flags() -> None:
    """Database setup must not receive Flask, Redis, or Entra runtime credentials."""
    migrate = load_compose("docker-compose.yml")["services"]["migrate"]

    assert "env_file" not in migrate
    assert migrate["environment"].get("APP_ENV") == "migration"
    assert migrate["environment"].get("DEMO_MODE") == "false"
    assert migrate["environment"].get("SEED_DEMO") == "false"
    assert migrate["environment"].get("DEMO_TODAY") == ""
    assert migrate["environment"].get("ENTRA_ENABLED") == "false"
    assert set(migrate["secrets"]) == {
        "postgres_owner_password",
        "postgres_app_password",
        "postgres_backup_password",
    }
    assert "FLASK_SECRET_KEY_FILE" not in migrate["environment"]
    assert "ENTRA_CLIENT_SECRET_FILE" not in migrate["environment"]
    assert set(migrate["environment"]).isdisjoint(
        {
            "ENTRA_TENANT_ID",
            "ENTRA_CLIENT_ID",
            "FLASK_SECRET_KEY_FILE",
            "ENTRA_CLIENT_SECRET_FILE",
            "REDIS_PASSWORD_FILE",
        }
    )


def test_migrate_configuration_loads_without_flask_or_entra_secrets(tmp_path: Path) -> None:
    """The real migration command must configure itself with database credentials alone."""
    migrate = load_compose("docker-compose.yml")["services"]["migrate"]
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "DATABASE_URL",
            "DATABASE_URL_FILE",
            "FLASK_SECRET_KEY",
            "FLASK_SECRET_KEY_FILE",
            "ENTRA_CLIENT_SECRET",
            "ENTRA_CLIENT_SECRET_FILE",
            "REDIS_PASSWORD",
            "REDIS_PASSWORD_FILE",
        }
    }
    environment.update(
        {
            "APP_ENV": "production",
            "DEMO_MODE": "false",
            "SEED_DEMO": "false",
            "DEMO_TODAY": "",
            "ENTRA_ENABLED": "true",
            "ENTRA_TENANT_ID": "11111111-1111-1111-1111-111111111111",
            "ENTRA_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        }
    )
    environment.update(
        {
            key: str(migrate["environment"].get(key, environment[key]))
            for key in ("APP_ENV", "DEMO_MODE", "SEED_DEMO", "DEMO_TODAY", "ENTRA_ENABLED")
        }
    )
    for variable in (
        "POSTGRES_PASSWORD_FILE",
        "POSTGRES_APP_PASSWORD_FILE",
        "POSTGRES_BACKUP_PASSWORD_FILE",
    ):
        secret_file = tmp_path / f"{variable.lower()}.txt"
        secret_file.write_text("database-secret\n", encoding="utf-8")
        environment[variable] = str(secret_file)

    result = subprocess.run(
        [sys.executable, str(ROOT / "reference_scaffold" / "manage.py"), "--help"],
        check=False,
        capture_output=True,
        cwd=ROOT / "reference_scaffold",
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "rejected_setting"),
    (
        ({"APP_PUBLIC_BASE_URL": f"http://{PRODUCTION_HOST}"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": "https://wrong.example"}, "APP_PUBLIC_BASE_URL"),
        (
            {"APP_PUBLIC_BASE_URL": f"https://{PRODUCTION_HOST}:443@wrong.example"},
            "APP_PUBLIC_BASE_URL",
        ),
        ({"APP_PUBLIC_BASE_URL": f"{PRODUCTION_ORIGIN}:443"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": f"{PRODUCTION_ORIGIN}:8443"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": f"{PRODUCTION_ORIGIN}/menu"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": f"{PRODUCTION_ORIGIN}?preview=1"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": f"{PRODUCTION_ORIGIN}#menu"}, "APP_PUBLIC_BASE_URL"),
        ({"APP_PUBLIC_BASE_URL": f"https://user@{PRODUCTION_HOST}"}, "APP_PUBLIC_BASE_URL"),
        ({"SESSION_COOKIE_SECURE": "false"}, "SESSION_COOKIE_SECURE"),
    ),
)
def test_production_entrypoint_rejects_insecure_public_origin(
    tmp_path: Path,
    overrides: dict[str, str],
    rejected_setting: str,
) -> None:
    """Production startup must enforce one HTTPS origin and secure session cookies."""
    production_settings = {"SESSION_COOKIE_SECURE": "true"} | overrides
    result = run_entrypoint(tmp_path, **production_settings)

    assert result.returncode != 0
    assert rejected_setting in result.stderr


def test_production_entrypoint_accepts_secure_matching_public_origin(tmp_path: Path) -> None:
    """A valid HTTPS origin with secure cookies must pass the deployment gate."""
    result = run_entrypoint(tmp_path, SESSION_COOKIE_SECURE="true")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "app_image",
    (
        "suedhang-cafeteria:local",
        "suedhang-cafeteria:latest",
        "registry.example.invalid/dishboard:production",
        "registry.example.invalid/dishboard@sha256:short",
        "",
    ),
)
def test_production_entrypoint_rejects_mutable_app_images(tmp_path: Path, app_image: str) -> None:
    """A production process must identify the exact image digest needed for rollback."""
    result = run_entrypoint(tmp_path, APP_IMAGE=app_image)

    assert result.returncode != 0
    assert "APP_IMAGE" in result.stderr


def _write_checksum(backup: Path, digest: str | None = None) -> Path:
    checksum = backup.with_name(f"{backup.name}.sha256")
    checksum.write_text(
        f"{digest or hashlib.sha256(backup.read_bytes()).hexdigest()}  {backup.name}\n",
        encoding="utf-8",
    )
    return checksum


def _run_restore(
    tmp_path: Path,
    *,
    checksum: bool = True,
    checksum_digest: str | None = None,
    docker_fail_match: str = "",
    staged_database: str = "cafeteria_restore_candidate",
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    backup = tmp_path / "cafeteria.dump"
    backup.write_bytes(b"safe candidate archive")
    if checksum:
        _write_checksum(backup, checksum_digest)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
if [ -n "${DOCKER_FAIL_MATCH:-}" ]; then
    case "$*" in
        *"$DOCKER_FAIL_MATCH"*) exit 42 ;;
    esac
fi
case "$*" in
    *restore-stage*) printf '%s\\n' "$STAGED_DATABASE" ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DOCKER_LOG": str(docker_log),
        "DOCKER_FAIL_MATCH": docker_fail_match,
        "STAGED_DATABASE": staged_database,
    }
    result = subprocess.run(
        ["/bin/sh", str(DEPLOYMENT / "restore.sh"), str(backup)],
        check=False,
        capture_output=True,
        cwd=DEPLOYMENT,
        env=environment,
        text=True,
    )
    calls = docker_log.read_text(encoding="utf-8").splitlines() if docker_log.exists() else []
    return result, calls


def test_restore_requires_a_checksum_before_contacting_docker(tmp_path: Path) -> None:
    """An unverified dump must not reach PostgreSQL or stop the running app."""
    result, calls = _run_restore(tmp_path, checksum=False)

    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()
    assert calls == []


def test_restore_rejects_a_checksum_mismatch_before_contacting_docker(tmp_path: Path) -> None:
    """A changed dump must be rejected before any deployment service is touched."""
    result, calls = _run_restore(tmp_path, checksum_digest="0" * 64)

    assert result.returncode != 0
    assert calls == []


def test_restore_validates_candidate_before_stopping_production(tmp_path: Path) -> None:
    """A failed staging restore leaves the live database and app untouched."""
    result, calls = _run_restore(tmp_path, docker_fail_match="restore-stage")

    assert result.returncode != 0
    assert any("restore-stage" in call for call in calls)
    assert not any("stop app backup" in call for call in calls)


def test_restore_uses_the_candidate_name_returned_by_the_restore_container(tmp_path: Path) -> None:
    """A POSTGRES_DB value loaded from Compose .env must drive candidate validation."""
    result, calls = _run_restore(
        tmp_path,
        staged_database="menuplan_restore_candidate",
    )

    assert result.returncode == 0, result.stderr
    assert any("POSTGRES_DB=menuplan_restore_candidate migrate" in call for call in calls)


def test_restore_cleans_an_invalid_candidate_before_stopping_production(tmp_path: Path) -> None:
    """Migration failure in staging must remove only the candidate database."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="POSTGRES_DB=cafeteria_restore_candidate migrate",
    )

    assert result.returncode != 0
    assert any("restore-cleanup-candidate" in call for call in calls)
    assert not any("stop app backup" in call for call in calls)


def test_restore_rolls_back_and_restarts_after_post_promotion_failure(tmp_path: Path) -> None:
    """A failed live validation restores the old database and starts services again."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="run --rm --no-deps app python /app/manage.py validate-db",
    )

    assert result.returncode != 0
    assert any("stop app backup" in call for call in calls)
    assert any("restore-promote" in call for call in calls)
    assert any("restore-rollback" in call for call in calls)
    assert any("up -d app backup" in call for call in calls)


def test_restore_restarts_services_when_promotion_fails(tmp_path: Path) -> None:
    """A failed database swap must not leave app and backup stopped."""
    result, calls = _run_restore(tmp_path, docker_fail_match="restore-promote")

    assert result.returncode != 0
    assert any("stop app backup" in call for call in calls)
    assert any("up -d app backup" in call for call in calls)


def test_restore_attempts_restart_when_stopping_services_fails(tmp_path: Path) -> None:
    """Even a partial stop failure must trigger the restart cleanup path."""
    result, calls = _run_restore(tmp_path, docker_fail_match="stop app backup")

    assert result.returncode != 0
    assert any("up -d app backup" in call for call in calls)


def test_backup_can_export_a_restore_ready_pair_to_an_absolute_host_path(tmp_path: Path) -> None:
    """Update rollback records must point to a host dump with its checksum sidecar."""
    export_dir = tmp_path / "rollback-backups"
    export_dir.mkdir()
    backup = export_dir / "cafeteria-20260901T120000Z.dump"
    backup.write_bytes(b"backup")
    _write_checksum(backup)
    fake_bin = tmp_path / "backup-bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "backup-docker.log"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
printf '%s\\n' '/export/cafeteria-20260901T120000Z.dump'
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DOCKER_LOG": str(docker_log),
    }

    result = subprocess.run(
        ["/bin/sh", str(DEPLOYMENT / "backup.sh"), str(export_dir)],
        check=False,
        capture_output=True,
        cwd=DEPLOYMENT,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(backup)
    assert f"-e BACKUP_DIR=/export -v {export_dir}:/export backup once" in docker_log.read_text(
        encoding="utf-8"
    )


def test_staging_pg_restore_failure_drops_only_candidate_database(tmp_path: Path) -> None:
    """The database-side cleanup trap must preserve production after pg_restore fails."""
    backup = tmp_path / "cafeteria.dump"
    backup.write_bytes(b"archive")
    checksum = _write_checksum(backup)
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("secret\n", encoding="utf-8")
    command_log = tmp_path / "commands.log"
    fake_bin = tmp_path / "postgres-bin"
    fake_bin.mkdir()

    for command in ("createdb", "dropdb", "psql"):
        executable = fake_bin / command
        executable.write_text(
            f"#!/bin/sh\nprintf '%s %s\\n' '{command}' \"$*\" >> \"$COMMAND_LOG\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    pg_restore = fake_bin / "pg_restore"
    pg_restore.write_text(
        """#!/bin/sh
printf '%s %s\\n' 'pg_restore' "$*" >> "$COMMAND_LOG"
case "$*" in
    *--list*) exit 0 ;;
esac
exit 23
""",
        encoding="utf-8",
    )
    pg_restore.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "POSTGRES_DB": "cafeteria",
        "POSTGRES_HOST": "db",
        "POSTGRES_USER": "cafeteria_owner",
        "POSTGRES_PASSWORD_FILE": str(password_file),
    }

    result = subprocess.run(
        [
            "/bin/sh",
            str(DEPLOYMENT / "postgres-backup.sh"),
            "restore-stage",
            str(backup),
            str(checksum),
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    calls = command_log.read_text(encoding="utf-8").splitlines()
    candidate_drops = [
        call
        for call in calls
        if call.startswith("dropdb ") and call.endswith(" cafeteria_restore_candidate")
    ]

    assert result.returncode == 23
    assert len(candidate_drops) >= 2
    assert not any(call.startswith("dropdb ") and call.endswith(" cafeteria") for call in calls)


def test_runbook_documents_immutable_image_and_database_compatible_rollback() -> None:
    """Operators need a recorded image+backup pair and an exact rollback sequence."""
    runbook = (ROOT / "docs" / "DOCKER_COMPOSE_RUNBOOK.md").read_text(encoding="utf-8")

    assert "cafeteria.suedhang.ch" not in runbook
    assert ".previous-app-image" in runbook
    assert "APP_IMAGE" in runbook
    assert "@sha256:" in runbook
    assert "restore.sh" in runbook


def test_direct_operator_scripts_are_executable() -> None:
    """Documented direct invocations must work from a fresh Git checkout."""
    for name in ("bootstrap.sh", "backup.sh", "restore.sh"):
        mode = stat.S_IMODE((DEPLOYMENT / name).stat().st_mode)
        assert mode == 0o755, f"{name}: expected mode 0755, got {mode:04o}"


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


def test_production_entrypoint_rejects_entra_placeholders_while_disabled(tmp_path: Path) -> None:
    """Disabling Entra must not make placeholder credentials valid for production startup."""
    result = run_entrypoint(
        tmp_path,
        secret_text="REPLACE_WITH_ENTRA_CLIENT_SECRET_FOR_PRODUCTION\n",
        ENTRA_ENABLED="false",
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
