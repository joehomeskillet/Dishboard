from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"


def test_failed_database_promotion_renames_the_old_database_back(tmp_path: Path) -> None:
    """A failure between the two database renames must recover the live database name."""
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("secret\n", encoding="utf-8")
    command_log = tmp_path / "promotion-commands.log"
    fake_bin = tmp_path / "promotion-bin"
    fake_bin.mkdir()
    dropdb = fake_bin / "dropdb"
    dropdb.write_text(
        "#!/bin/sh\nprintf '%s %s\\n' 'dropdb' \"$*\" >> \"$COMMAND_LOG\"\n",
        encoding="utf-8",
    )
    dropdb.chmod(0o755)
    psql = fake_bin / "psql"
    psql.write_text(
        """#!/bin/sh
printf '%s %s\\n' 'psql' "$*" >> "$COMMAND_LOG"
case "$*" in
    *"datname = 'cafeteria_restore_candidate_recovery'"*) printf '%s\\n' 'menuplan-restore:recovery' ;;
    *pg_database*) printf '%s\\n' '<absent>' ;;
    *'ALTER DATABASE "cafeteria_restore_candidate_recovery" RENAME TO "cafeteria";'*) exit 31 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    psql.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "POSTGRES_DB": "cafeteria",
        "POSTGRES_HOST": "db",
        "POSTGRES_USER": "cafeteria_owner",
        "POSTGRES_PASSWORD_FILE": str(password_file),
        "RESTORE_RUN_ID": "recovery",
    }

    result = subprocess.run(
        ["/bin/sh", str(DEPLOYMENT / "postgres-backup.sh"), "restore-promote"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    calls = command_log.read_text(encoding="utf-8")

    assert result.returncode == 31
    assert 'ALTER DATABASE "cafeteria" RENAME TO "cafeteria_restore_rollback_recovery";' in calls
    assert 'ALTER DATABASE "cafeteria_restore_rollback_recovery" RENAME TO "cafeteria";' in calls
    assert 'ALTER DATABASE "cafeteria" ALLOW_CONNECTIONS true;' in calls


def _run_stage_with_existing_candidate(tmp_path: Path, marker: str) -> tuple[subprocess.CompletedProcess[str], str]:
    backup = tmp_path / "cafeteria.dump"
    backup.write_bytes(b"archive")
    checksum = backup.with_name(f"{backup.name}.sha256")
    checksum.write_text(
        f"{hashlib.sha256(backup.read_bytes()).hexdigest()}  {backup.name}\n",
        encoding="utf-8",
    )
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("secret\n", encoding="utf-8")
    command_log = tmp_path / "stage-commands.log"
    fake_bin = tmp_path / "stage-bin"
    fake_bin.mkdir()
    for command in ("createdb", "dropdb"):
        executable = fake_bin / command
        executable.write_text(
            f"#!/bin/sh\nprintf '%s %s\\n' '{command}' \"$*\" >> \"$COMMAND_LOG\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    psql = fake_bin / "psql"
    database_state = marker or "<absent>"
    psql.write_text(
        f"""#!/bin/sh
printf '%s %s\\n' 'psql' "$*" >> "$COMMAND_LOG"
case "$*" in
    *pg_database*) printf '%s\\n' '{database_state}' ;;
    *CREATE\\ EXTENSION*) printf '%s\\n' 'ready' ;;
    *public.digest*) printf '%s\\n' 'ready' ;;
    *to_regnamespace*) printf '%s\\n' 'ready' ;;
esac
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
        "RESTORE_RUN_ID": "unit",
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
    return result, command_log.read_text(encoding="utf-8")


def test_restore_stage_refuses_a_foreign_candidate_without_drop(tmp_path: Path) -> None:
    """A reused run id must never terminate or drop a database without this run's marker."""
    result, calls = _run_stage_with_existing_candidate(tmp_path, "foreign-restore-owner")

    assert result.returncode != 0
    assert "fremde" in result.stderr.lower()
    assert "dropdb" not in calls


def test_restore_stage_installs_and_verifies_pgcrypto_before_candidate_is_ready(tmp_path: Path) -> None:
    """A schema-only dump cannot rely on template0 to provide public.pgcrypto."""
    result, calls = _run_stage_with_existing_candidate(tmp_path, "")

    assert result.returncode == 0, result.stderr
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public" in calls
    assert "digest(" in calls
