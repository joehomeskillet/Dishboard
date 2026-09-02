from __future__ import annotations

import time

import pytest

from test_deployment_restore_live import (
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


def _reapply_fixture_permissions(drill: RestoreDrill, database: str) -> None:
    drill.sql(
        database,
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA cafeteria "
        "FROM PUBLIC, cafeteria_app, cafeteria_backup;",
    )


def test_postgres16_writer_release_crash_keeps_candidate_and_resets_tokens(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    drill = postgres16_restore_drill
    run_id = "writer_release_crash"
    token = drill.script("restore-acquire", run_id).stdout.strip()
    holder = drill.start_holder(
        run_id,
        token,
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    candidate = drill.script(
        "restore-stage",
        f"/work/{drill.dump_name}",
        f"/work/{drill.checksum_name}",
        run_id,
        token,
    ).stdout.strip()
    drill.script("restore-state", run_id, token, "migrated")
    _reapply_fixture_permissions(drill, candidate)
    drill.script("restore-ensure-auth-capabilities", run_id, token, candidate)
    _reapply_fixture_permissions(drill, candidate)
    drill.script("restore-reset-auth-capabilities", run_id, token, candidate)
    drill.script("restore-state", run_id, token, "candidate_validated")
    drill.script("restore-promote", run_id, token)
    drill.script("restore-state", run_id, token, "live_validated")
    drill.script("restore-state", run_id, token, "writer_release_committed")
    drill.sql("cafeteria", "INSERT INTO cafeteria.restore_drill VALUES ('ponr-write');")
    consumed_token = drill.sql(
        "cafeteria",
        "SELECT cafeteria.issue_auth_capability_token('ponr-consumed');",
    )
    unused_token = drill.sql(
        "cafeteria",
        "SELECT cafeteria.issue_auth_capability_token('ponr-unused');",
    )
    assert drill.sql(
        "cafeteria",
        f"SELECT cafeteria.consume_auth_capability_token('{consumed_token}');",
    ) == "t"
    docker("rm", "--force", holder)
    time.sleep(3)

    takeover = drill.script(
        "restore-recovery-acquire",
        "ponr_recovery",
        extra_environment=("--env", "RESTORE_CONTROLLER_TIMEOUT_SECONDS=2"),
    )
    restored_run, replacement_token, action = takeover.stdout.split()
    assert (restored_run, action) == (run_id, "recover")
    recovery_holder = drill.start_holder(run_id, replacement_token)
    try:
        drill.script("restore-recover", run_id, replacement_token)
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
            "postgres",
            "SELECT recovery_target FROM public.menuplan_restore_control "
            "WHERE database_name='cafeteria';",
        ) == "candidate"
        assert drill.sql(
            "cafeteria",
            "SELECT count(*) FROM cafeteria.restore_drill WHERE value='ponr-write';",
        ) == "1"
        rollback = f"cafeteria_restore_rollback_{run_id}"
        assert drill.sql(
            "postgres",
            "SELECT (NOT datallowconn) AND shobj_description(oid, 'pg_database') LIKE "
            "'menuplan-restore-rollback:%' FROM pg_database "
            f"WHERE datname='{rollback}';",
        ) == "t"
        for old_token in (consumed_token, unused_token):
            assert drill.sql(
                "cafeteria",
                f"SELECT cafeteria.consume_auth_capability_token('{old_token}');",
            ) == "f"
        new_token = drill.sql(
            "cafeteria",
            "SELECT cafeteria.issue_auth_capability_token('ponr-new');",
        )
        assert drill.sql(
            "cafeteria",
            f"SELECT cafeteria.consume_auth_capability_token('{new_token}');",
        ) == "t"
        drill.script("restore-state", run_id, replacement_token, "app_validated")
        drill.script("restore-state", run_id, replacement_token, "complete")
        drill.script("restore-complete-services-running", run_id, replacement_token)
    finally:
        docker("rm", "--force", recovery_holder, check=False)
