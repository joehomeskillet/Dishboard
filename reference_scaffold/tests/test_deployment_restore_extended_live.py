from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import time

import pytest

from test_deployment_restore_live import (
    PG_IMAGE,
    RUN_LIVE_DRILL,
    RestoreDrill,
    docker,
    postgres16_restore_drill_fixture,
)


__all__ = ("postgres16_restore_drill_fixture",)
pytestmark = pytest.mark.skipif(
    not RUN_LIVE_DRILL,
    reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill",
)


def _start_candidate(drill: RestoreDrill, run_id: str) -> tuple[str, str, str]:
    owner_token = drill.script("restore-acquire", run_id).stdout.strip()
    holder_name = drill.start_holder(run_id, owner_token)
    candidate = drill.script(
        "restore-stage",
        f"/work/{drill.dump_name}",
        f"/work/{drill.checksum_name}",
        run_id,
        owner_token,
    ).stdout.strip()
    return owner_token, holder_name, candidate


def _reapply_fixture_permissions(drill: RestoreDrill, candidate: str) -> None:
    drill.sql(
        candidate,
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA cafeteria "
        "FROM PUBLIC, cafeteria_app, cafeteria_backup;",
    )


def test_postgres16_holder_sigkill_and_dead_controller_fail_closed(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "holder_sigkill"
    owner_token = drill.script("restore-acquire", run_id).stdout.strip()
    holder_name = drill.start_holder(
        run_id,
        owner_token,
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    assert drill.sql(
        "postgres",
        "SELECT lease_expires_at > clock_timestamp() FROM public.menuplan_restore_control "
        "WHERE database_name='cafeteria';",
    ) == "t"

    docker("rm", "--force", holder_name)
    dead_holder = drill.script(
        "restore-assert-held",
        run_id,
        owner_token,
        check=False,
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    assert dead_holder.returncode != 0
    time.sleep(3)
    takeover = drill.script(
        "restore-recovery-acquire",
        "replacement_controller",
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    restored_run, replacement_token, action = takeover.stdout.split()
    assert (restored_run, action) == (run_id, "recover")
    replacement_holder = drill.start_holder(
        run_id,
        replacement_token,
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    try:
        drill.script("restore-abort", run_id, replacement_token)
    finally:
        docker("rm", "--force", replacement_holder, check=False)

    second_run = "controller_dead"
    second_token = drill.script("restore-acquire", second_run).stdout.strip()
    orphan_candidate = drill.start_holder(
        second_run,
        second_token,
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    time.sleep(4)
    assert docker("inspect", orphan_candidate, check=False).returncode != 0
    assert drill.sql(
        "postgres",
        "SELECT count(*) FROM pg_stat_activity WHERE "
        "application_name LIKE 'menuplan_restore_holder:%';",
    ) == "0"
    second_takeover = drill.script(
        "restore-recovery-acquire",
        "replacement_after_controller",
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    second_restored_run, second_replacement_token, second_action = second_takeover.stdout.split()
    assert (second_restored_run, second_action) == (second_run, "recover")
    final_holder = drill.start_holder(second_run, second_replacement_token)
    try:
        drill.script("restore-abort", second_run, second_replacement_token)
    finally:
        docker("rm", "--force", final_holder, check=False)


def test_postgres16_short_holder_lease_renews_with_margin(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "short_holder_lease"
    lease_environment = (
        "--env",
        "RESTORE_LEASE_SECONDS=3",
        "--env",
        "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2",
    )
    token = drill.script(
        "restore-acquire",
        run_id,
        extra_environment=lease_environment,
    ).stdout.strip()
    holder = drill.start_holder(run_id, token, extra_environment=lease_environment)
    try:
        for _attempt in range(5):
            time.sleep(0.8)
            drill.script(
                "restore-assert-held",
                run_id,
                token,
                extra_environment=lease_environment,
            )
        assert drill.sql(
            "postgres",
            "SELECT lease_expires_at > clock_timestamp() FROM public.menuplan_restore_control "
            "WHERE database_name='cafeteria';",
        ) == "t"
        drill.script("restore-abort", run_id, token, extra_environment=lease_environment)
    finally:
        docker("rm", "--force", holder, check=False)


def test_postgres16_controller_death_before_holder_attach_is_recoverable(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "dead_before_holder"
    timeout_environment = ("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2")
    original_token = drill.script(
        "restore-acquire",
        run_id,
        extra_environment=timeout_environment,
    ).stdout.strip()
    immediate = drill.script(
        "restore-recovery-acquire",
        "premature_recovery",
        check=False,
        extra_environment=timeout_environment,
    )
    assert immediate.returncode != 0
    time.sleep(3)
    takeover = drill.script(
        "restore-recovery-acquire",
        "replacement_before_holder",
        extra_environment=timeout_environment,
    )
    restored_run, replacement_token, action = takeover.stdout.split()
    assert (restored_run, action) == (run_id, "recover")
    assert replacement_token != original_token
    holder = drill.start_holder(run_id, replacement_token)
    try:
        drill.script("restore-abort", run_id, replacement_token)
    finally:
        docker("rm", "--force", holder, check=False)


def test_postgres16_stage_failures_abort_without_candidate_or_noop_progress(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    invalid = drill.work_dir / "invalid.dump"
    invalid.write_bytes(b"not a PostgreSQL archive")
    invalid.with_name(f"{invalid.name}.sha256").write_text(
        f"{hashlib.sha256(invalid.read_bytes()).hexdigest()}  {invalid.name}\n",
        encoding="utf-8",
    )
    run_id = "invalid_archive"
    token = drill.script("restore-acquire", run_id).stdout.strip()
    holder = drill.start_holder(run_id, token)
    try:
        failed = drill.script(
            "restore-stage",
            "/work/invalid.dump",
            "/work/invalid.dump.sha256",
            run_id,
            token,
            check=False,
        )
        assert failed.returncode != 0
        assert drill.sql(
            "postgres",
            "SELECT lifecycle FROM public.menuplan_restore_control "
            "WHERE database_name='cafeteria';",
        ) == "aborted"
        assert drill.sql(
            "postgres",
            "SELECT count(*) FROM pg_database WHERE "
            "datname='cafeteria_restore_candidate_invalid_archive';",
        ) == "0"
    finally:
        docker("rm", "--force", holder, check=False)

    noop_run = "stage_noop"
    noop_token = drill.script("restore-acquire", noop_run).stdout.strip()
    noop_holder = drill.start_holder(noop_run, noop_token)
    try:
        drill.sql(
            "postgres",
            "UPDATE public.menuplan_restore_control SET lifecycle='staging' "
            "WHERE database_name='cafeteria';",
        )
        noop = drill.script(
            "restore-stage",
            f"/work/{drill.dump_name}",
            f"/work/{drill.checksum_name}",
            noop_run,
            noop_token,
            check=False,
        )
        assert noop.returncode != 0
        assert drill.sql(
            "postgres",
            "SELECT lifecycle FROM public.menuplan_restore_control "
            "WHERE database_name='cafeteria';",
        ) == "aborted"
    finally:
        docker("rm", "--force", noop_holder, check=False)


def test_postgres16_backup_role_exclusion_ensure_permissions_and_hard_reset(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    archive = docker(
        "run",
        "--rm",
        "--volume",
        f"{drill.work_dir}:/work:ro",
        PG_IMAGE,
        "pg_restore",
        "--list",
        f"/work/{drill.dump_name}",
    ).stdout
    assert "auth_capability_secrets" not in archive
    assert "auth_capability_nonces" not in archive

    run_id = "capability_reset"
    owner_token, holder, candidate = _start_candidate(drill, run_id)
    try:
        assert drill.sql(
            candidate,
            "SELECT to_regclass('cafeteria.auth_capability_secrets') IS NULL "
            "AND to_regclass('cafeteria.auth_capability_nonces') IS NULL;",
        ) == "t"
        drill.script("restore-state", run_id, owner_token, "migrated")
        _reapply_fixture_permissions(drill, candidate)
        drill.script("restore-ensure-auth-capabilities", run_id, owner_token, candidate)
        _reapply_fixture_permissions(drill, candidate)
        drill.script("restore-reset-auth-capabilities", run_id, owner_token, candidate)

        assert drill.sql(
            candidate,
            "SELECT (SELECT count(*) FROM cafeteria.auth_capability_secrets) = 1 "
            "AND (SELECT count(*) FROM cafeteria.auth_capability_secrets WHERE active) = 1 "
            "AND NOT EXISTS (SELECT 1 FROM cafeteria.auth_capability_nonces);",
        ) == "t"
        assert drill.sql(
            candidate,
            "SELECT cafeteria.consume_auth_capability_token(" f"'{drill.old_token}');",
        ) == "f"
        assert drill.sql(
            candidate,
            "SELECT cafeteria.consume_auth_capability_token(" f"'{drill.unused_token}');",
        ) == "f"
        fresh_token = drill.sql(
            candidate,
            "SELECT cafeteria.issue_auth_capability_token('fresh-after-restore');",
        )
        assert drill.sql(
            candidate,
            f"SELECT cafeteria.consume_auth_capability_token('{fresh_token}');",
        ) == "t"
        assert drill.sql(
            candidate,
            f"SELECT cafeteria.consume_auth_capability_token('{fresh_token}');",
        ) == "f"
        assert drill.sql(
            candidate,
            "SELECT bool_and(NOT has_function_privilege('cafeteria_app', p.oid, 'EXECUTE') "
            "AND NOT has_function_privilege('cafeteria_backup', p.oid, 'EXECUTE') "
            "AND NOT EXISTS (SELECT 1 FROM aclexplode(COALESCE(p.proacl, "
            "acldefault('f', p.proowner))) x WHERE x.grantee = 0 "
            "AND x.privilege_type = 'EXECUTE')) FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='cafeteria' "
            "AND p.prosecdef AND p.proname IN ('ensure_auth_capability_state', "
            "'hard_reset_auth_capability_state', 'bootstrap_auth_capability_secret', "
            "'rotate_auth_capability_secret', 'sync_auth_capability_state', "
            "'issue_auth_capability_token', 'withdraw_auth_capability');",
        ) == "t"
        drill.script("restore-abort", run_id, owner_token)
    finally:
        docker("rm", "--force", holder, check=False)


def test_postgres16_old_proof_survives_crash_before_marker_removal(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "proof_crash"
    token, holder, _candidate = _start_candidate(drill, run_id)
    try:
        drill.script("restore-state", run_id, token, "migrated")
        drill.script("restore-state", run_id, token, "candidate_validated")
        promotion = drill.script(
            "restore-promote",
            run_id,
            token,
            check=False,
            extra_environment=(
                "--env",
                "RESTORE_FAIL_AFTER_STATE=production_renamed",
                "--env",
                "RESTORE_TESTING=true",
            ),
        )
        assert promotion.returncode != 0
        recovery = drill.script(
            "restore-recover",
            run_id,
            token,
            check=False,
            extra_environment=(
                "--env",
                "RESTORE_FAIL_AFTER_STATE=old_database_proof_persisted",
                "--env",
                "RESTORE_TESTING=true",
            ),
        )
        assert recovery.returncode != 0
        assert drill.sql(
            "postgres",
            "SELECT old_database_verified::text || '|' || lifecycle FROM "
            "public.menuplan_restore_control WHERE database_name='cafeteria';",
        ) == "true|old_database_proof_persisted"
        assert drill.sql(
            "postgres",
            "SELECT shobj_description(oid, 'pg_database') LIKE "
            "'menuplan-restore-rollback:%' FROM pg_database WHERE datname='cafeteria';",
        ) == "t"
        drill.script("restore-recover", run_id, token)
        _reapply_fixture_permissions(drill, "cafeteria")
        drill.script("restore-ensure-auth-capabilities", run_id, token, "production")
        _reapply_fixture_permissions(drill, "cafeteria")
        drill.script("restore-reset-auth-capabilities", run_id, token, "production")
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{drill.old_token}');",
        ) == "f"
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{drill.unused_token}');",
        ) == "f"
        assert drill.sql(
            "postgres",
            "SELECT lifecycle FROM public.menuplan_restore_control "
            "WHERE database_name='cafeteria';",
        ) == "recovery_ready"
    finally:
        docker("rm", "--force", holder, check=False)


def test_postgres16_post_writer_complete_resume_and_retention_prune(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "post_writer"
    token, holder, candidate = _start_candidate(drill, run_id)
    drill.script("restore-state", run_id, token, "migrated")
    _reapply_fixture_permissions(drill, candidate)
    drill.script("restore-ensure-auth-capabilities", run_id, token, candidate)
    _reapply_fixture_permissions(drill, candidate)
    drill.script("restore-reset-auth-capabilities", run_id, token, candidate)
    drill.script("restore-state", run_id, token, "candidate_validated")
    drill.script("restore-promote", run_id, token)
    drill.script("restore-state", run_id, token, "live_validated")
    drill.script("restore-state", run_id, token, "writer_release_committed")
    drill.sql("cafeteria", "INSERT INTO cafeteria.restore_drill VALUES ('post-writer');")
    consumed_after_writer = drill.sql(
        "cafeteria",
        "SELECT cafeteria.issue_auth_capability_token('consumed-after-writer');",
    )
    unused_after_writer = drill.sql(
        "cafeteria",
        "SELECT cafeteria.issue_auth_capability_token('unused-after-writer');",
    )
    assert drill.sql(
        "cafeteria",
        f"SELECT cafeteria.consume_auth_capability_token('{consumed_after_writer}');",
    ) == "t"
    drill.script("restore-state", run_id, token, "app_validated")
    drill.script("restore-state", run_id, token, "complete")
    docker("rm", "--force", holder)

    resume = drill.script("restore-recovery-acquire", "resume_controller")
    restored_run, replacement_token, action = resume.stdout.split()
    assert (restored_run, action) == (run_id, "resume")
    replacement_holder = drill.start_holder(run_id, replacement_token)
    try:
        drill.script("restore-assert-complete-target", run_id, replacement_token)
        _reapply_fixture_permissions(drill, "cafeteria")
        drill.script(
            "restore-ensure-auth-capabilities",
            run_id,
            replacement_token,
            "production",
        )
        _reapply_fixture_permissions(drill, "cafeteria")
        drill.script(
            "restore-reset-auth-capabilities",
            run_id,
            replacement_token,
            "production",
        )
        assert drill.sql(
            "cafeteria",
            "SELECT count(*) FROM cafeteria.restore_drill WHERE value='post-writer';",
        ) == "1"
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{consumed_after_writer}');",
        ) == "f"
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{unused_after_writer}');",
        ) == "f"
        new_token = drill.sql(
            "cafeteria",
            "SELECT cafeteria.issue_auth_capability_token('new-after-resume');",
        )
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{new_token}');",
        ) == "t"
        drill.script("restore-complete-services-running", run_id, replacement_token)
    finally:
        docker("rm", "--force", replacement_holder, check=False)

    rollback = f"cafeteria_restore_rollback_{run_id}"
    marker = drill.sql(
        "postgres",
        "SELECT rollback_marker FROM public.menuplan_restore_retained "
        f"WHERE rollback_database='{rollback}';",
    )
    drill.sql(
        "postgres",
        "UPDATE public.menuplan_restore_retained SET retain_until=clock_timestamp() - interval '1 second' "
        f"WHERE rollback_database='{rollback}'; COMMENT ON DATABASE \"{rollback}\" IS 'foreign';",
    )
    foreign = drill.script("restore-prune-retained", check=False)
    assert foreign.returncode != 0
    assert drill.sql(
        "postgres",
        f"SELECT count(*) FROM pg_database WHERE datname='{rollback}';",
    ) == "1"
    drill.sql("postgres", f'COMMENT ON DATABASE "{rollback}" IS \'{marker}\';')
    drill.script("restore-prune-retained")
    assert drill.sql(
        "postgres",
        f"SELECT count(*) FROM pg_database WHERE datname='{rollback}';",
    ) == "0"
    assert drill.sql(
        "postgres",
        "SELECT count(*) FROM public.menuplan_restore_audit WHERE "
        f"restore_run_id='{run_id}' AND event='rollback_retention_pruned';",
    ) == "1"
    reused = drill.script("restore-acquire", run_id, check=False)
    assert reused.returncode != 0
    assert "already used" in reused.stderr


def test_postgres16_concurrent_backup_role_runs_use_distinct_pairs(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill

    def backup() -> str:
        return drill.script(
            "once",
            extra_environment=(
                "--env",
                "BACKUP_DIR=/work",
                *drill.backup_environment,
            ),
        ).stdout.strip()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(executor.map(lambda _index: backup(), range(2)))

    assert len(set(outputs)) == 2
    for output in outputs:
        dump = drill.work_dir / output.rsplit("/", 1)[-1]
        assert dump.is_file()
        assert dump.with_name(f"{dump.name}.sha256").is_file()
        assert dump.with_name(f"{dump.name}.json").is_file()
