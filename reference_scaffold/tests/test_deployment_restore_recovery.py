from __future__ import annotations

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
    *'ALTER DATABASE "cafeteria_restore_candidate" RENAME TO "cafeteria";'*) exit 31 ;;
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
    assert 'ALTER DATABASE "cafeteria" RENAME TO "cafeteria_restore_rollback";' in calls
    assert 'ALTER DATABASE "cafeteria_restore_rollback" RENAME TO "cafeteria";' in calls
    assert 'ALTER DATABASE "cafeteria" ALLOW_CONNECTIONS true;' in calls
