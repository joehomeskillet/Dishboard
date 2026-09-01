#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from cafeteria.config import Config
from cafeteria.db import init_database, validate_database


def wait_for_database(database_url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    last_error: Exception | None = None
    try:
        while time.monotonic() < deadline:
            try:
                with engine.connect() as connection:
                    connection.execute(text('SELECT 1')).scalar_one()
                return
            except OperationalError as exc:
                last_error = exc
                time.sleep(1)
    finally:
        engine.dispose()
    raise RuntimeError(f'PostgreSQL nicht erreichbar: {type(last_error).__name__ if last_error else "timeout"}')


def main() -> int:
    cfg = Config()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    init_cmd = sub.add_parser('init-db')
    init_cmd.add_argument('--wait-seconds', type=int, default=60)
    seed_cmd = sub.add_parser('seed-demo')
    seed_cmd.add_argument('--wait-seconds', type=int, default=60)
    validate_cmd = sub.add_parser('validate-db')
    validate_cmd.add_argument('--wait-seconds', type=int, default=10)
    wait_cmd = sub.add_parser('wait-db')
    wait_cmd.add_argument('--wait-seconds', type=int, default=60)
    args = parser.parse_args()

    wait_for_database(cfg.DATABASE_URL, args.wait_seconds)
    if args.command == 'wait-db':
        print('PostgreSQL erreichbar.')
        return 0

    if args.command == 'init-db':
        status = init_database(
            cfg.DATABASE_URL,
            cfg.SCHEMA_PATH,
            cfg.SEED_PATH,
            permissions_path=cfg.PERMISSIONS_PATH,
            demo_seed_path=cfg.DEMO_SEED_PATH,
            app_password=cfg.POSTGRES_APP_PASSWORD,
            backup_password=cfg.POSTGRES_BACKUP_PASSWORD,
            seed_demo=cfg.DEMO_MODE and cfg.SEED_DEMO,
        )
    elif args.command == 'seed-demo':
        status = init_database(
            cfg.DATABASE_URL,
            cfg.SCHEMA_PATH,
            cfg.SEED_PATH,
            permissions_path=cfg.PERMISSIONS_PATH,
            demo_seed_path=cfg.DEMO_SEED_PATH,
            app_password=cfg.POSTGRES_APP_PASSWORD,
            backup_password=cfg.POSTGRES_BACKUP_PASSWORD,
            seed_demo=True,
        )
    else:
        engine = create_engine(cfg.DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
        try:
            status = validate_database(engine)
        finally:
            engine.dispose()

    print(json.dumps(status, ensure_ascii=False, indent=2, default=str))
    return 0 if status.get('ready') else 1


if __name__ == '__main__':
    raise SystemExit(main())
