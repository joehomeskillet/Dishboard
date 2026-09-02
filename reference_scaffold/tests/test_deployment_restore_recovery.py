from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
OWNER_TOKEN = "11111111-1111-4111-8111-111111111111"


def _deployment_script(name: str) -> str:
    return (DEPLOYMENT / name).read_text(encoding="utf-8")


def _postgres_restore_scripts() -> str:
    return _deployment_script("postgres-backup.sh") + _deployment_script(
        "postgres-restore-control.sh"
    )


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
    *"SELECT recovery_target"*) printf '%s\\n' 'old' ;;
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


def test_holder_is_a_live_backend_fence_without_division_sentinels() -> None:
    """The lease proof must identify one connected backend that owns the advisory lock."""
    script = _postgres_restore_scripts()

    assert "holder_backend_pid" in script
    assert "holder_backend_start" in script
    assert "pg_stat_activity" in script
    assert "pg_locks" in script
    assert "lease_heartbeat_seconds=$((LEASE_SECONDS / 3))" in script
    assert "1 / 0" not in script


def test_controller_watchdog_proves_the_holder_before_destructive_steps() -> None:
    """A dead holder must be observed while the controller is still mutating topology."""
    script = _deployment_script("restore.sh")

    assert "start_lease_watchdog" in script
    assert "assert_lease_holder" in script
    assert script.count("assert_lease_holder") >= 8
    assert "controller_heartbeat" in script


def test_writer_release_has_a_durable_point_of_no_return() -> None:
    """No writer starts until rollback direction is durably committed."""
    script = _deployment_script("restore.sh")

    barrier = script.index("writer_release_committed")
    release_call = script.index("start_and_validate_app", barrier)
    backup_start = script.index("start_backup_and_record_complete", release_call)
    helper = script[script.index("start_and_validate_app()") : script.index("recover_database_and_app()")]
    app_start = helper.index("up -d --wait --no-deps app")
    app_validated = helper.index("app_validated", app_start)
    complete = helper.index(" complete", app_validated)
    assert barrier < release_call < backup_start
    assert app_start < app_validated < complete
    assert "up -d app backup" not in script


def test_terminal_complete_can_resume_services_without_database_rollback() -> None:
    """A crash after complete has a fenced, idempotent service-only recovery path."""
    host = _deployment_script("restore.sh")
    control = _deployment_script("postgres-restore-control.sh")

    assert "restore-recovery-acquire" in host
    assert "resume_completed_services" in host
    resume = host[host.index("resume_completed_services()") : host.index("recover_database_and_app()")]
    assert "restore-assert-complete-target" in resume
    assert "restore-recover" not in resume
    assert "up -d --no-deps backup" not in resume
    assert "start_backup_and_record_complete" in resume
    assert "complete_resume_acquired" in control
    assert "restore_assert_complete_target" in control


def test_every_production_recovery_reapplies_acl_around_capability_hard_reset() -> None:
    """Old, candidate, and terminal-complete recovery close PUBLIC before repair."""
    host = _deployment_script("restore.sh")
    repair = host[host.index("repair_production_capabilities()") : host.index("resume_completed_services()")]
    first_permissions = repair.index("run --rm --no-deps migrate")
    ensure = repair.index("restore-ensure-auth-capabilities", first_permissions)
    second_permissions = repair.index("run --rm --no-deps migrate", ensure)
    hard_reset = repair.index("restore-reset-auth-capabilities", second_permissions)

    assert first_permissions < ensure < second_permissions < hard_reset
    assert "repair_production_capabilities" in host[
        host.index("resume_completed_services()") : host.index("recover_database_and_app()")
    ]
    assert "repair_production_capabilities" in host[
        host.index("recover_database_and_app()") : host.index("if [ \"$PRUNE_MODE\"")
    ]


def test_recovery_persists_old_database_proof_before_removing_marker() -> None:
    """A crash cannot erase the only rollback proof before it is durable in control DB."""
    script = _postgres_restore_scripts()
    recovery = script.index("restore_recover_topology()")
    proof = script.index("old_database_verified = true", recovery)
    restore_comment = script.index("COMMENT ON DATABASE", recovery)

    assert proof < restore_comment
    assert "old_database_proof_persisted" in script[proof:restore_comment]


def test_stage_cleanup_precedes_archive_inspection_and_lifecycle_mutation() -> None:
    """Bad archives must leave an abort path before staging state is entered."""
    script = _deployment_script("postgres-backup.sh")
    stage = script[script.index("restore_stage()") : script.index("restore_promote()")]

    trap_index = stage.index("trap cleanup_staging_failure 0")
    list_index = stage.index("pg_restore --list")
    staging_index = stage.index("restore_state_internal=staging")
    assert trap_index < list_index < staging_index


def test_conditional_lifecycle_updates_assert_exactly_one_row() -> None:
    """Stage and recovery may not continue after a stale no-op UPDATE."""
    script = _deployment_script("postgres-backup.sh")
    stage = script[script.index("restore_stage()") : script.index("restore_promote()")]
    recovery = script[script.index("restore_recover_topology()") :]

    assert stage.count("count(*) = 1") >= 2
    assert recovery.count("count(*) = 1") >= 2


def test_backups_are_collision_safe_and_rollback_retention_is_audited() -> None:
    """Concurrent backups and retained rollback databases need unique, bounded ownership."""
    script = _postgres_restore_scripts()

    assert "mktemp" in script[script.index("backup_once()") : script.index("verify_checksum()")]
    assert "menuplan_restore_retained" in script
    assert "retain_until" in script
    assert "rollback_retention_pruned" in script
    assert "Restore run id was already used" in script
    assert "COALESCE(c.controller_heartbeat_at, c.updated_at)" in script


def test_backups_exclude_capability_state_and_restore_requires_hard_reset() -> None:
    """A restored dump must contain no reusable capability key or replay nonce."""
    script = _deployment_script("postgres-backup.sh")
    control = _deployment_script("postgres-restore-control.sh")

    assert "--exclude-table=cafeteria.auth_capability_secrets" in script
    assert "--exclude-table=cafeteria.auth_capability_nonces" in script
    assert "--exclude-table=cafeteria.auth_capability_secrets_id_seq" in script
    assert "cafeteria.hard_reset_auth_capability_state()" in control
    assert "cafeteria.ensure_auth_capability_state()" in control
    assert "hard_reset_result <> 1" in control
    assert "count(*) FROM cafeteria.auth_capability_secrets" in control
    reset = control[control.index("restore_reset_auth_capabilities()") :]
    assert "rotate_auth_capability_secret" not in reset
    assert "bootstrap_auth_capability_secret" not in reset
    assert "DELETE FROM cafeteria.auth_capability_nonces" not in reset
    host = _deployment_script("restore.sh")
    migrated = host.index('restore-state "$restore_run_id" "$owner_token" migrated')
    ensure = host.index("restore-ensure-auth-capabilities", migrated)
    permissions = host.index('POSTGRES_DB=$candidate_database" migrate', ensure)
    hard_reset = host.index("restore-reset-auth-capabilities", permissions)
    validation = host.index("validate-db --wait-seconds 30", hard_reset)
    assert migrated < ensure < permissions < hard_reset < validation


def test_old_database_proof_has_a_tested_crash_boundary_before_comment_removal() -> None:
    """The persisted proof can be interrupted before the rollback marker is removed."""
    script = _deployment_script("postgres-backup.sh")
    proof = script[script.index("persist_old_database_proof()") :]

    assert "RESTORE_FAIL_AFTER_STATE" in proof
    assert "old_database_proof_persisted" in proof
    assert proof.index("old_database_proof_persisted") < proof.index("COMMENT ON DATABASE")
