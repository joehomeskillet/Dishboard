from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESTORE_SCRIPT = ROOT / "deployment" / "postgres-backup.sh"
RUN_LIVE_DRILL = os.getenv("RUN_LIVE_RESTORE_DRILL") == "1"


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
            "pg_isready",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    pytest.fail("PostgreSQL 16 drill database did not become ready within 60 seconds")


@pytest.mark.skipif(not RUN_LIVE_DRILL, reason="set RUN_LIVE_RESTORE_DRILL=1 for the PostgreSQL 16 drill")
def test_postgres16_backup_stage_promote_and_forced_validation_rollback(tmp_path: Path) -> None:
    """A real PostgreSQL 16 dump returns the original, connection-enabled database after validation fails."""
    resource_id = uuid4().hex[:12]
    network_name = f"menuplan-restore-{resource_id}"
    database_name = f"menuplan-pg16-{resource_id}"
    run_id = f"live_{resource_id}"
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text("restore-drill-owner\n", encoding="utf-8")
    mount = f"{tmp_path}:/work"
    script_mount = f"{RESTORE_SCRIPT}:/usr/local/bin/postgres-backup.sh:ro"
    common_environment = (
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
        f"RESTORE_RUN_ID={run_id}",
    )

    docker("network", "create", network_name)
    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            database_name,
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
            "postgres:16-alpine",
        )
        wait_for_postgres(database_name)
        docker(
            "exec",
            database_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            "--set=ON_ERROR_STOP=1",
            "--command=CREATE EXTENSION pgcrypto; CREATE SCHEMA cafeteria; CREATE TABLE cafeteria.restore_drill (value text); INSERT INTO cafeteria.restore_drill VALUES ('original');",
        )
        docker(
            "run",
            "--rm",
            "--network",
            network_name,
            "--volume",
            mount,
            "--volume",
            script_mount,
            *common_environment,
            "--env",
            "BACKUP_DIR=/work",
            "postgres:16-alpine",
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            "once",
        )
        dump = next(tmp_path.glob("cafeteria-*.dump"))
        checksum = dump.with_name(f"{dump.name}.sha256")
        stage = docker(
            "run",
            "--rm",
            "--network",
            network_name,
            "--volume",
            mount,
            "--volume",
            script_mount,
            *common_environment,
            "postgres:16-alpine",
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            "restore-stage",
            f"/work/{dump.name}",
            f"/work/{checksum.name}",
        )
        candidate = stage.stdout.strip()
        assert candidate == f"cafeteria_restore_candidate_{run_id}"
        digest_check = docker(
            "exec",
            database_name,
            "psql",
            "--username=cafeteria_owner",
            f"--dbname={candidate}",
            "--tuples-only",
            "--no-align",
            "--command=SELECT encode(public.digest(convert_to('drill', 'UTF8'), 'sha256'), 'hex');",
        )
        assert len(digest_check.stdout.strip()) == 64
        docker(
            "run",
            "--rm",
            "--network",
            network_name,
            "--volume",
            mount,
            "--volume",
            script_mount,
            *common_environment,
            "postgres:16-alpine",
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            "restore-promote",
        )
        forced_failure = docker(
            "exec",
            database_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            "--set=ON_ERROR_STOP=1",
            "--command=SELECT 1 / 0;",
            check=False,
        )
        assert forced_failure.returncode != 0
        docker(
            "run",
            "--rm",
            "--network",
            network_name,
            "--volume",
            mount,
            "--volume",
            script_mount,
            *common_environment,
            "postgres:16-alpine",
            "/bin/sh",
            "/usr/local/bin/postgres-backup.sh",
            "restore-rollback",
        )
        restored = docker(
            "exec",
            database_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=cafeteria",
            "--tuples-only",
            "--no-align",
            "--command=SELECT value FROM cafeteria.restore_drill;",
        )
        allow_connections = docker(
            "exec",
            database_name,
            "psql",
            "--username=cafeteria_owner",
            "--dbname=postgres",
            "--tuples-only",
            "--no-align",
            "--command=SELECT datallowconn FROM pg_database WHERE datname='cafeteria';",
        )
        assert restored.stdout.strip() == "original"
        assert allow_connections.stdout.strip() == "t"
    finally:
        docker("rm", "--force", database_name, check=False)
        docker("network", "rm", network_name, check=False)
