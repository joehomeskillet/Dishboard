from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESTORE_SCRIPT = ROOT / "deployment" / "postgres-backup.sh"
RUN_LIVE_DRILL = os.getenv("RUN_LIVE_RESTORE_DRILL") == "1"
PG_IMAGE = "postgres:16-alpine"


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def wait_for_postgres(container_name: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = docker(
            "exec",
            container_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            "--command=SELECT 1;",
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    pytest.fail("PostgreSQL 16 drill database did not become ready within 60 seconds")


@dataclass(frozen=True)
class RestoreDrill:
    container_name: str
    network_name: str
    work_dir: Path
    environment: tuple[str, ...]

    def script(
        self,
        *arguments: str,
        check: bool = True,
        extra_environment: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        return docker(
            "run",
            "--rm",
            "--network",
            self.network_name,
            "--volume",
            f"{self.work_dir}:/work",
            "--volume",
            f"{RESTORE_SCRIPT}:/usr/local/bin/postgres-backup.sh:ro",
            *self.environment,
            *extra_environment,
            PG_IMAGE,
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            *arguments,
            check=check,
        )

    def sql(self, database: str, statement: str) -> str:
        result = docker(
            "exec",
            self.container_name,
            "psql",
            "--username=cafeteria_owner",
            f"--dbname={database}",
            "--set=ON_ERROR_STOP=1",
            "--tuples-only",
            "--no-align",
            f"--command={statement}",
        )
        return result.stdout.strip()

    def start_holder(self, run_id: str, owner_token: str) -> str:
        holder_name = f"menuplan-holder-{uuid4().hex[:12]}"
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            holder_name,
            "--network",
            self.network_name,
            "--volume",
            f"{self.work_dir}:/work",
            "--volume",
            f"{RESTORE_SCRIPT}:/usr/local/bin/postgres-backup.sh:ro",
            *self.environment,
            PG_IMAGE,
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            "restore-hold",
            run_id,
            owner_token,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            event = self.sql(
                "postgres",
                "SELECT last_event FROM public.menuplan_restore_control WHERE database_name='cafeteria';",
            )
            if event in {"lease_held", "lease_heartbeat"}:
                return holder_name
            time.sleep(0.2)
        pytest.fail("restore lease holder did not establish its PostgreSQL advisory lock")

    @property
    def dump_name(self) -> str:
        return next(self.work_dir.glob("cafeteria-*.dump")).name

    @property
    def checksum_name(self) -> str:
        return f"{self.dump_name}.sha256"


@pytest.fixture
def postgres16_restore_drill(tmp_path: Path) -> RestoreDrill:
    resource_id = uuid4().hex[:12]
    network_name = f"menuplan-restore-{resource_id}"
    container_name = f"menuplan-pg16-{resource_id}"
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("restore-drill-owner\n", encoding="utf-8")
    environment = (
        "--env",
        "POSTGRES_HOST=pg",
        "--env",
        "POSTGRES_PORT=5432",
        "--env",
        "POSTGRES_DB=cafeteria",
        "--env",
        "POSTGRES_USER=cafeteria_owner",
        "--env",
        "POSTGRES_PASSWORD_FILE=/work/owner-password.txt",
        "--env",
        "RESTORE_LEASE_SECONDS=60",
    )

    docker("network", "create", network_name)
    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--network",
            network_name,
            "--network-alias",
            "pg",
            "--env",
            "POSTGRES_USER=cafeteria_owner",
            "--env",
            "POSTGRES_PASSWORD=restore-drill-owner",
            "--env",
            "POSTGRES_DB=cafeteria",
            PG_IMAGE,
        )
        wait_for_postgres(container_name)
        docker(
            "exec",
            container_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            "--set=ON_ERROR_STOP=1",
            "--command=CREATE EXTENSION pgcrypto; CREATE SCHEMA cafeteria; CREATE TABLE cafeteria.restore_drill (value text); INSERT INTO cafeteria.restore_drill VALUES ('original');",
        )
        drill = RestoreDrill(container_name, network_name, tmp_path, environment)
        drill.script("once", extra_environment=("--env", "BACKUP_DIR=/work"))
        yield drill
    finally:
        docker("rm", "--force", container_name, check=False)
        docker("network", "rm", network_name, check=False)


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_cluster_lease_denies_a_second_restore_host(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    """A lease in PostgreSQL, not a host lock file, serializes independent restore hosts."""
    drill = postgres16_restore_drill
    first = drill.script("restore-acquire", "host_one")
    owner_token = first.stdout.strip()
    holder_name = drill.start_holder("host_one", owner_token)
    try:
        second = drill.script("restore-acquire", "host_two", check=False)

        assert len(owner_token) == 36
        assert second.returncode != 0
        assert "lease" in second.stderr.lower()
        owner = drill.sql(
            "postgres",
            "SELECT owner_run_id FROM public.menuplan_restore_control WHERE database_name='cafeteria';",
        )
        assert owner == "host_one"
    finally:
        docker("rm", "--force", holder_name, check=False)
    drill.script("restore-abort", "host_one", owner_token)


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_expired_lease_requires_an_audited_recovery_takeover(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    """An incomplete expired lease is recoverable only through an explicit token rotation."""
    drill = postgres16_restore_drill
    original = drill.script(
        "restore-acquire",
        "expired_owner",
        extra_environment=("--env", "RESTORE_LEASE_SECONDS=1"),
    )
    original_token = original.stdout.strip()
    skipped_stage = drill.script(
        "restore-state",
        "expired_owner",
        original_token,
        "migrated",
        check=False,
    )
    assert skipped_stage.returncode != 0
    time.sleep(2)

    normal_acquire = drill.script("restore-acquire", "new_restore", check=False)
    takeover = drill.script("restore-takeover", "recovery_host")
    restore_run_id, replacement_token = takeover.stdout.split()
    stale_owner = drill.script(
        "restore-abort",
        "expired_owner",
        original_token,
        check=False,
    )

    assert normal_acquire.returncode != 0
    assert restore_run_id == "expired_owner"
    assert replacement_token != original_token
    assert stale_owner.returncode != 0
    assert drill.sql(
        "postgres",
        "SELECT owner_run_id || '|' || last_event FROM public.menuplan_restore_control WHERE database_name='cafeteria';",
    ) == "recovery_host|lease_expired_takeover"
    assert drill.sql(
        "postgres",
        "SELECT event FROM public.menuplan_restore_audit WHERE database_name='cafeteria' ORDER BY event_id DESC LIMIT 1;",
    ) == "lease_expired_takeover"
    drill.script("restore-abort", restore_run_id, replacement_token)


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_partial_promotion_failure_recovers_only_the_old_database(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    """A failure after the old-name move is recovered from durable state, never from the candidate."""
    drill = postgres16_restore_drill
    run_id = "partial_failure"
    owner_token = drill.script("restore-acquire", run_id).stdout.strip()
    stage = drill.script(
        "restore-stage",
        f"/work/{drill.dump_name}",
        f"/work/{drill.checksum_name}",
        run_id,
        owner_token,
    )
    assert stage.stdout.strip() == f"cafeteria_restore_candidate_{run_id}"
    drill.script("restore-state", run_id, owner_token, "migrated")
    drill.script("restore-state", run_id, owner_token, "candidate_validated")

    promotion = drill.script(
        "restore-promote",
        run_id,
        owner_token,
        check=False,
        extra_environment=(
            "--env",
            "RESTORE_FAIL_AFTER_STATE=production_renamed",
            "--env",
            "RESTORE_TESTING=true",
        ),
    )
    assert promotion.returncode != 0
    assert drill.sql(
        "postgres",
        "SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='cafeteria');",
    ) == "t"

    drill.script("restore-recover", run_id, owner_token)
    drill.script("restore-recover", run_id, owner_token)

    assert drill.sql("cafeteria", "SELECT value FROM cafeteria.restore_drill;") == "original"
    assert drill.sql(
        "postgres",
        "SELECT datallowconn FROM pg_database WHERE datname='cafeteria';",
    ) == "t"
    assert drill.sql(
        "cafeteria",
        "SELECT to_regprocedure('public.digest(bytea,text)') IS NOT NULL AND to_regnamespace('cafeteria') IS NOT NULL;",
    ) == "t"
    assert drill.sql(
        "postgres",
        "SELECT lifecycle FROM public.menuplan_restore_control WHERE database_name='cafeteria';",
    ) == "recovery_ready"


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_promotion_refuses_a_foreign_rollback_database(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    """A pre-existing rollback name is never terminated, renamed, or dropped by this run."""
    drill = postgres16_restore_drill
    run_id = "foreign_marker"
    owner_token = drill.script("restore-acquire", run_id).stdout.strip()
    drill.script(
        "restore-stage",
        f"/work/{drill.dump_name}",
        f"/work/{drill.checksum_name}",
        run_id,
        owner_token,
    )
    drill.script("restore-state", run_id, owner_token, "migrated")
    drill.script("restore-state", run_id, owner_token, "candidate_validated")
    rollback = f"cafeteria_restore_rollback_{run_id}"
    drill.sql("postgres", f'CREATE DATABASE "{rollback}";')
    drill.sql("postgres", f'COMMENT ON DATABASE "{rollback}" IS \'foreign-owner\';')

    promotion = drill.script("restore-promote", run_id, owner_token, check=False)

    assert promotion.returncode != 0
    assert "foreign" in promotion.stderr.lower() or "vorhanden" in promotion.stderr.lower()
    assert drill.sql("cafeteria", "SELECT value FROM cafeteria.restore_drill;") == "original"
    assert drill.sql(
        "postgres",
        f"SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname='{rollback}';",
    ) == "foreign-owner"


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_abort_refuses_a_foreign_pending_candidate(
    postgres16_restore_drill: RestoreDrill,
) -> None:
    """A create-pending crash cannot claim and drop a database created by another actor."""
    drill = postgres16_restore_drill
    run_id = "foreign_pending"
    owner_token = drill.script("restore-acquire", run_id).stdout.strip()
    candidate = f"cafeteria_restore_candidate_{run_id}"
    drill.sql(
        "postgres",
        "UPDATE public.menuplan_restore_control SET lifecycle='candidate_create_pending' "
        "WHERE database_name='cafeteria';",
    )
    drill.sql("postgres", f'CREATE DATABASE "{candidate}";')
    drill.sql("postgres", f'COMMENT ON DATABASE "{candidate}" IS \'foreign-owner\';')

    abort = drill.script("restore-abort", run_id, owner_token, check=False)

    assert abort.returncode != 0
    assert drill.sql(
        "postgres",
        f"SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname='{candidate}';",
    ) == "foreign-owner"
