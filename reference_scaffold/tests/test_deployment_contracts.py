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
LOCAL_APP_IMAGE = "sha256:" + ("2" * 64)


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
    issuer_secret_file = tmp_path / "postgres_auth_issuer_password.txt"
    issuer_secret_file.write_text(
        "Issuer-Role-2026-Z8yW6uT4sR2qP9nM\n",
        encoding="utf-8",
    )
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
        "POSTGRES_AUTH_ISSUER_PASSWORD_FILE": str(issuer_secret_file),
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
    assert compose["services"]["app"]["ports"] == [
        "127.0.0.1:${APP_HOST_PORT:-8789}:8000"
    ]


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
    assert environment["APP_IMAGE"] == "sha256:REPLACE_WITH_LOCAL_IMAGE_ID"
    assert environment["APP_HOST_PORT"] == "8789"
    assert environment["LOCAL_AUTH_ENABLED"] == "true"
    assert environment["ENTRA_ENABLED"] == "false"


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
        "postgres_auth_issuer_password",
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
    role_secrets = {
        "POSTGRES_PASSWORD_FILE": "Owner-Role-2026-A7bQ9xV4kM2rP8tN",
        "POSTGRES_APP_PASSWORD_FILE": "App-Role-2026-B8cR7yW5uN3sQ9vK",
        "POSTGRES_BACKUP_PASSWORD_FILE": "Backup-Role-2026-C9dS8zX6vP4tR2wL",
        "POSTGRES_AUTH_ISSUER_PASSWORD_FILE": "Issuer-Role-2026-D2eT9aY7wQ5uS3xM",
    }
    for variable, role_secret in role_secrets.items():
        secret_file = tmp_path / f"{variable.lower()}.txt"
        secret_file.write_text(role_secret + "\n", encoding="utf-8")
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


def test_production_entrypoint_accepts_local_content_addressed_image(tmp_path: Path) -> None:
    result = run_entrypoint(tmp_path, APP_IMAGE=LOCAL_APP_IMAGE)

    assert result.returncode == 0, result.stderr


def test_compose_mounts_one_dedicated_auth_issuer_secret_and_no_url() -> None:
    compose = load_compose('docker-compose.yml')
    issuer_secret = 'postgres_auth_issuer_password'

    assert compose['secrets'][issuer_secret]['file'] == (
        './secrets/postgres_auth_issuer_password.txt'
    )
    for service_name in ('migrate', 'app'):
        service = compose['services'][service_name]
        assert service['environment']['POSTGRES_AUTH_ISSUER_PASSWORD_FILE'] == (
            '/run/secrets/postgres_auth_issuer_password'
        )
        assert service['secrets'].count(issuer_secret) == 1
        assert 'AUTH_ISSUER_DATABASE_URL' not in service['environment']
    for service_name in ('db', 'backup', 'restore'):
        assert issuer_secret not in compose['services'][service_name].get('secrets', [])


def test_bootstrap_generates_one_stable_strong_auth_issuer_secret(tmp_path: Path) -> None:
    deployment = tmp_path / 'deployment'
    deployment.mkdir()
    shutil.copy2(DEPLOYMENT / 'bootstrap.sh', deployment / 'bootstrap.sh')
    shutil.copy2(DEPLOYMENT / '.env.example', deployment / '.env.example')

    first = subprocess.run(
        ['/bin/sh', str(deployment / 'bootstrap.sh')],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    issuer_files = list((deployment / 'secrets').glob('postgres_auth_issuer_password*.txt'))
    assert len(issuer_files) == 1
    first_value = issuer_files[0].read_text(encoding='utf-8').strip()
    assert len(first_value) >= 32

    second = subprocess.run(
        ['/bin/sh', str(deployment / 'bootstrap.sh')],
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert issuer_files[0].read_text(encoding='utf-8').strip() == first_value


def test_production_entrypoint_rejects_missing_or_weak_auth_issuer_secret(
    tmp_path: Path,
) -> None:
    missing = run_entrypoint(
        tmp_path,
        POSTGRES_AUTH_ISSUER_PASSWORD_FILE=str(tmp_path / 'missing-issuer-secret.txt'),
    )
    assert missing.returncode != 0
    assert 'POSTGRES_AUTH_ISSUER_PASSWORD_FILE' in missing.stderr

    weak_file = tmp_path / 'weak-issuer-secret.txt'
    weak_file.write_text('x\n', encoding='utf-8')
    weak = run_entrypoint(
        tmp_path,
        POSTGRES_AUTH_ISSUER_PASSWORD_FILE=str(weak_file),
    )
    assert weak.returncode != 0
    assert 'POSTGRES_AUTH_ISSUER_PASSWORD_FILE' in weak.stderr


def test_proxy_network_uses_exact_deterministic_peers_without_broad_cidr() -> None:
    compose = load_compose('docker-compose.yml')
    overlay = load_compose('docker-compose.caddy.yml')
    network = compose['networks']['cafeteria_internal']
    subnet = network['ipam']['config'][0]

    assert subnet == {'subnet': '10.213.0.0/24', 'gateway': '10.213.0.1'}
    assert compose['services']['app']['networks']['cafeteria_internal']['ipv4_address'] == (
        '10.213.0.20'
    )
    assert overlay['services']['caddy']['networks']['cafeteria_internal']['ipv4_address'] == (
        '10.213.0.10'
    )
    assert compose['services']['app']['environment']['TRUSTED_PROXY_PEERS'] == (
        '10.213.0.1,10.213.0.10'
    )
    assert 'TRUSTED_PROXY_CIDRS' not in compose['services']['app']['environment']
    assert 'TRUSTED_PROXY_HOPS' not in compose['services']['app']['environment']


def test_host_caddy_example_proxies_only_to_loopback_app_port() -> None:
    caddyfile = (DEPLOYMENT / 'caddy' / 'Caddyfile.host.example').read_text(encoding='utf-8')

    assert 'dishboard.joelduss.xyz {' in caddyfile
    assert 'reverse_proxy 127.0.0.1:8789' in caddyfile
    assert 'reverse_proxy app:8000' not in caddyfile
    assert 'import authelia' not in caddyfile


@pytest.mark.parametrize(
    "app_image",
    (
        "suedhang-cafeteria:local",
        "suedhang-cafeteria:latest",
        "registry.example.invalid/dishboard:production",
        "registry.example.invalid/dishboard@sha256:short",
        "sha256:short",
        "sha256:" + ("A" * 64),
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
    docker_fail_second_match: str = "",
    staged_database: str = "cafeteria_restore_candidate_test_run",
    extra_environment: dict[str, str] | None = None,
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
if [ -n "${DOCKER_FAIL_SECOND_MATCH:-}" ]; then
    case "$*" in
        *"$DOCKER_FAIL_SECOND_MATCH"*) exit 43 ;;
    esac
fi
case "$*" in
    *restore-acquire*) printf '%s\\n' '11111111-1111-4111-8111-111111111111' ;;
    *restore-hold*) printf '%s\\n' 'fake-lease-container' ;;
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
        "DOCKER_FAIL_SECOND_MATCH": docker_fail_second_match,
        "STAGED_DATABASE": staged_database,
        "RESTORE_RUN_ID": "test_run",
    }
    if extra_environment:
        environment.update(extra_environment)
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
        staged_database="menuplan_restore_candidate_test_run",
    )

    assert result.returncode == 0, result.stderr
    assert any("POSTGRES_DB=menuplan_restore_candidate_test_run migrate" in call for call in calls)


def test_restore_cleans_an_invalid_candidate_before_stopping_production(tmp_path: Path) -> None:
    """Migration failure in staging must remove only the candidate database."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="POSTGRES_DB=cafeteria_restore_candidate_test_run migrate",
    )

    assert result.returncode != 0
    assert any("restore-abort" in call for call in calls)
    assert not any("stop app backup" in call for call in calls)


def test_restore_rolls_back_and_restarts_after_post_promotion_failure(tmp_path: Path) -> None:
    """A failed live validation restarts only after control-DB recovery and revalidation."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="run --rm --no-deps app python /app/manage.py validate-db",
    )

    assert result.returncode != 0
    assert any("stop app backup" in call for call in calls)
    assert any("restore-promote" in call for call in calls)
    recovery_index = next(index for index, call in enumerate(calls) if "restore-recover" in call)
    restart_index = next(
        index for index, call in enumerate(calls) if "up -d --wait --no-deps app" in call
    )
    backup_index = next(
        index for index, call in enumerate(calls) if "up -d --no-deps backup" in call
    )
    assert recovery_index < restart_index < backup_index
    assert any("RESTORE_RECOVERY_VALIDATION=true" in call for call in calls)
    assert any("restore-state test_run" in call and " complete" in call for call in calls)


def test_restore_does_not_restart_the_app_when_rollback_cannot_be_validated(tmp_path: Path) -> None:
    """A failed rollback leaves services stopped instead of serving an unvalidated candidate."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="run --rm --no-deps app python /app/manage.py validate-db",
        docker_fail_second_match="restore-recover",
    )

    assert result.returncode != 0
    assert any("restore-recover" in call for call in calls)
    assert not any("up -d --wait --no-deps app" in call for call in calls)


def test_restore_acquires_a_database_lease_before_staging(tmp_path: Path) -> None:
    """The first PostgreSQL operation must acquire the cluster-wide restore lease."""
    result, calls = _run_restore(tmp_path)

    assert result.returncode == 0, result.stderr
    acquire_index = next(index for index, call in enumerate(calls) if "restore-acquire" in call)
    stage_index = next(index for index, call in enumerate(calls) if "restore-stage" in call)
    assert acquire_index < stage_index
    assert "11111111-1111-4111-8111-111111111111" in calls[stage_index]


def test_restore_stops_when_the_database_lease_is_held_elsewhere(tmp_path: Path) -> None:
    """A foreign cluster-wide lease must block staging and service changes."""
    result, calls = _run_restore(tmp_path, docker_fail_match="restore-acquire")

    assert result.returncode != 0
    assert any("restore-acquire" in call for call in calls)
    assert not any("restore-stage" in call for call in calls)
    assert not any("stop app backup" in call for call in calls)


def test_restore_keeps_services_stopped_when_promotion_recovery_is_unknown(tmp_path: Path) -> None:
    """A failed database swap may not restart services unless control-DB recovery succeeds."""
    result, calls = _run_restore(
        tmp_path,
        docker_fail_match="restore-promote",
        docker_fail_second_match="restore-recover",
    )

    assert result.returncode != 0
    assert any("stop app backup" in call for call in calls)
    assert any("restore-recover" in call for call in calls)
    assert not any("up -d --wait --no-deps app" in call for call in calls)


def test_restore_restarts_after_failed_promotion_only_when_recovery_is_proven(tmp_path: Path) -> None:
    """A separate successful recovery and old-database validation permit restart."""
    result, calls = _run_restore(tmp_path, docker_fail_match="restore-promote")

    assert result.returncode != 0
    recovery_index = next(index for index, call in enumerate(calls) if "restore-recover" in call)
    validation_index = next(
        index for index, call in enumerate(calls) if "RESTORE_RECOVERY_VALIDATION=true" in call
    )
    restart_index = next(
        index for index, call in enumerate(calls) if "up -d --wait --no-deps app" in call
    )
    backup_index = next(
        index for index, call in enumerate(calls) if "up -d --no-deps backup" in call
    )
    assert recovery_index < validation_index < restart_index < backup_index


def test_restore_keeps_services_stopped_when_the_stop_state_is_unknown(tmp_path: Path) -> None:
    """A partial stop failure may not be converted into an unconditional restart."""
    result, calls = _run_restore(tmp_path, docker_fail_match="stop app backup")

    assert result.returncode != 0
    assert not any("up -d --wait --no-deps app" in call for call in calls)


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

    for command in ("createdb", "dropdb"):
        executable = fake_bin / command
        executable.write_text(
            f"#!/bin/sh\nprintf '%s %s\\n' '{command}' \"$*\" >> \"$COMMAND_LOG\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    psql = fake_bin / "psql"
    psql.write_text(
        """#!/bin/sh
printf '%s %s\\n' 'psql' "$*" >> "$COMMAND_LOG"
case "$*" in
    *"datname = 'cafeteria_restore_candidate_staging'"*)
        if [ -f "$CANDIDATE_MARKER" ]; then printf '%s\\n' 'menuplan-restore:staging'; else printf '%s\\n' '<absent>'; fi
        ;;
    *'COMMENT ON DATABASE "cafeteria_restore_candidate_staging"'*) touch "$CANDIDATE_MARKER" ;;
esac
while IFS= read -r sql_line; do
    printf '%s %s\\n' 'sql' "$sql_line" >> "$COMMAND_LOG"
done
""",
        encoding="utf-8",
    )
    psql.chmod(0o755)
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
        "RESTORE_RUN_ID": "staging",
        "CANDIDATE_MARKER": str(tmp_path / "candidate-owned"),
    }

    result = subprocess.run(
        [
            "/bin/sh",
            str(DEPLOYMENT / "postgres-backup.sh"),
            "restore-stage",
            str(backup),
            str(checksum),
            "staging",
            "11111111-1111-4111-8111-111111111111",
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    calls = command_log.read_text(encoding="utf-8").splitlines()
    candidate_drops = [call for call in calls if 'DROP DATABASE :"candidate_db"' in call]

    assert result.returncode == 23
    assert len(candidate_drops) == 1
    assert not any('DROP DATABASE :"database_name"' in call for call in calls)


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


def test_restore_control_library_is_packaged_and_shell_parseable() -> None:
    """Both PostgreSQL utility services must see the sourced lease implementation."""
    compose = load_compose("docker-compose.yml")
    mount = "./postgres-restore-control.sh:/usr/local/bin/postgres-restore-control.sh:ro"

    assert mount in compose["services"]["backup"]["volumes"]
    assert mount in compose["services"]["restore"]["volumes"]
    for name in ("postgres-backup.sh", "postgres-restore-control.sh", "restore.sh"):
        result = subprocess.run(
            ["/bin/sh", "-n", str(DEPLOYMENT / name)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"


def test_restore_rejects_a_watchdog_period_that_can_expire_its_holder(tmp_path: Path) -> None:
    """The controller must pulse faster than the holder's configured timeout."""
    result, calls = _run_restore(
        tmp_path,
        extra_environment={
            "RESTORE_CONTROLLER_HEARTBEAT_SECONDS": "30",
            "RESTORE_CONTROLLER_TIMEOUT_SECONDS": "30",
        },
    )

    assert result.returncode != 0
    assert "RESTORE_CONTROLLER_HEARTBEAT_SECONDS" in result.stderr
    assert calls == []


def test_retention_prune_is_installed_as_a_bounded_daily_oneshot() -> None:
    """Expired owned rollback databases must not depend on operator memory."""
    service = DEPLOYMENT / "systemd" / "dishboard-retention-prune.service"
    timer = DEPLOYMENT / "systemd" / "dishboard-retention-prune.timer"
    runbook = (ROOT / "docs" / "DOCKER_COMPOSE_RUNBOOK.md").read_text(encoding="utf-8")

    service_text = service.read_text(encoding="utf-8")
    timer_text = timer.read_text(encoding="utf-8")
    assert "restore.sh --prune-retained" in service_text
    assert "Type=oneshot" in service_text
    assert "OnCalendar=daily" in timer_text
    assert "Persistent=true" in timer_text
    assert "dishboard-retention-prune.timer" in runbook


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


def test_production_entrypoint_allows_entra_placeholders_while_disabled(tmp_path: Path) -> None:
    """A disabled Entra provider must not block a local-only production deployment."""
    result = run_entrypoint(
        tmp_path,
        secret_text="REPLACE_WITH_ENTRA_CLIENT_SECRET_FOR_PRODUCTION\n",
        ENTRA_ENABLED="false",
        ENTRA_TENANT_ID="00000000-0000-0000-0000-000000000000",
        ENTRA_CLIENT_ID="00000000-0000-0000-0000-000000000000",
    )

    assert result.returncode == 0, result.stderr


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
