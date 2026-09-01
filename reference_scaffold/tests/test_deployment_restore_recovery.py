from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
OWNER_TOKEN = "11111111-1111-4111-8111-111111111111"


def _fake_postgres_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("secret\n", encoding="utf-8")
    command_log = tmp_path / "postgres-commands.log"
    fake_bin = tmp_path / "postgres-bin"
    fake_bin.mkdir()

    psql = fake_bin / "psql"
    psql.write_text(
        """#!/bin/sh
input=$(cat)
printf '%s %s\\n%s\\n' 'psql' "$*" "$input" >> "$COMMAND_LOG"
case "$*" in
    *public.digest*) printf '%s\\n' 'ready' ;;
esac
case "$input" in
    *"THEN 'allowed' ELSE 'blocked'"*) printf '%s\\n' 'allowed' ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    psql.chmod(0o755)
    pg_restore = fake_bin / "pg_restore"
    pg_restore.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    pg_restore.chmod(0o755)

    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "POSTGRES_DB": "cafeteria",
        "POSTGRES_HOST": "db",
        "POSTGRES_USER": "cafeteria_owner",
        "POSTGRES_PASSWORD_FILE": str(password_file),
    }
    return environment, command_log


def _run_mode(
    tmp_path: Path,
    mode: str,
    *arguments: str,
) -> tuple[subprocess.CompletedProcess[str], str]:
    environment, command_log = _fake_postgres_environment(tmp_path)
    result = subprocess.run(
        ["/bin/sh", str(DEPLOYMENT / "postgres-backup.sh"), mode, *arguments],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    calls = command_log.read_text(encoding="utf-8") if command_log.exists() else ""
    return result, calls


def test_restore_mutations_require_an_owner_token_before_postgres(tmp_path: Path) -> None:
    """A run id alone can no longer authorize any promotion mutation."""
    result, calls = _run_mode(tmp_path, "restore-promote", "missing_token")

    assert result.returncode != 0
    assert "token" in result.stderr.lower()
    assert calls == ""


def test_promotion_sql_holds_the_cluster_gate_and_persists_pending_states(tmp_path: Path) -> None:
    """The emitted promotion transaction fences takeover and records every crash boundary."""
    result, calls = _run_mode(tmp_path, "restore-promote", "promotion", OWNER_TOKEN)

    assert result.returncode == 0, result.stderr
    assert "pg_advisory_lock_shared" in calls
    assert "owner_token = :'owner_token'::uuid" in calls
    assert "lease_expires_at > clock_timestamp()" in calls
    assert "candidate_marker" in calls
    assert "rollback_absent" in calls
    assert calls.index("production_rename_pending") < calls.index('RENAME TO :"rollback_db"')
    assert calls.index("candidate_promote_pending") < calls.index('RENAME TO :"database_name"')


def test_recovery_sql_requires_the_marked_old_database_and_never_assumes_candidate(tmp_path: Path) -> None:
    """Recovery topology accepts only the durable rollback marker as the old database proof."""
    result, calls = _run_mode(tmp_path, "restore-recover", "recovery", OWNER_TOKEN)

    assert result.returncode == 0, result.stderr
    assert "production_is_candidate" in calls
    assert "rollback_owned" in calls
    assert "Alter Datenbankstand fehlt; Kandidat wird nicht als Recovery angenommen" in calls
    assert "recovery_topology_restored" in calls
    assert "public.digest" in calls
    assert "recovery_ready" in calls


def test_restore_stage_installs_pgcrypto_and_uses_a_tokenized_candidate_marker(tmp_path: Path) -> None:
    """Staging retains pgcrypto while binding the candidate database to the lease resource token."""
    backup = tmp_path / "cafeteria.dump"
    backup.write_bytes(b"archive")
    checksum = backup.with_name(f"{backup.name}.sha256")
    checksum.write_text(
        f"{hashlib.sha256(backup.read_bytes()).hexdigest()}  {backup.name}\n",
        encoding="utf-8",
    )
    result, calls = _run_mode(
        tmp_path,
        "restore-stage",
        str(backup),
        str(checksum),
        "staging",
        OWNER_TOKEN,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cafeteria_restore_candidate_staging"
    assert "menuplan-restore-candidate:" in calls
    assert 'CREATE DATABASE :"candidate_db" TEMPLATE template0' in calls
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public" in calls


def test_restore_abort_checks_the_candidate_marker_before_drop(tmp_path: Path) -> None:
    """Candidate cleanup emits no drop until marker ownership and lease validity are checked."""
    result, calls = _run_mode(tmp_path, "restore-abort", "cleanup", OWNER_TOKEN)

    assert result.returncode == 0, result.stderr
    ownership_check = calls.index("candidate_owned")
    drop_database = calls.index('DROP DATABASE :"candidate_db"')
    assert ownership_check < drop_database
    assert 'DROP DATABASE :"database_name"' not in calls
