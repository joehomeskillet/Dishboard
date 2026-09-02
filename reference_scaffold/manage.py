#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from cafeteria.auth.issuer import disable_local_user, provision_local_user, set_local_password
from cafeteria.config import Config
from cafeteria.db import ENTRA_APPLICATION_ROLES, init_database, validate_database


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


def _prompt_confirmed_password() -> str:
    password = getpass.getpass('Lokales Passwort: ')
    confirmation = getpass.getpass('Lokales Passwort wiederholen: ')
    if password != confirmation:
        raise RuntimeError('Passwortbestätigung stimmt nicht überein.')
    return password


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if any(value == '--password' or value.startswith('--password=') for value in arguments):
        raise RuntimeError('Lokale Passwörter dürfen nur interaktiv eingegeben werden.')
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
    local_cmd = sub.add_parser('provision-local-user')
    local_cmd.add_argument('--wait-seconds', type=int, default=10)
    local_cmd.add_argument('--username', required=True)
    local_cmd.add_argument('--display-name', required=True)
    local_cmd.add_argument(
        '--role',
        action='append',
        required=True,
        choices=sorted(ENTRA_APPLICATION_ROLES),
    )
    password_cmd = sub.add_parser('set-local-password')
    password_cmd.add_argument('--wait-seconds', type=int, default=10)
    password_cmd.add_argument('--username', required=True)
    disable_cmd = sub.add_parser('disable-local-user')
    disable_cmd.add_argument('--wait-seconds', type=int, default=10)
    disable_cmd.add_argument('--username', required=True)
    args = parser.parse_args(arguments)

    if args.command in {'provision-local-user', 'set-local-password', 'disable-local-user'}:
        if not cfg.AUTH_ISSUER_DATABASE_URL:
            raise RuntimeError('AUTH_ISSUER_DATABASE_URL fehlt.')
        wait_for_database(cfg.AUTH_ISSUER_DATABASE_URL, args.wait_seconds)
        engine = create_engine(
            cfg.AUTH_ISSUER_DATABASE_URL,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        try:
            if args.command == 'provision-local-user':
                user_id = provision_local_user(
                    engine,
                    username=args.username,
                    display_name=args.display_name,
                    password=_prompt_confirmed_password(),
                    roles=args.role,
                )
                action = 'provisioned'
            elif args.command == 'set-local-password':
                user_id = set_local_password(
                    engine,
                    username=args.username,
                    password=_prompt_confirmed_password(),
                )
                action = 'password_changed'
            else:
                user_id = disable_local_user(engine, username=args.username)
                action = 'disabled'
        finally:
            engine.dispose()
        print(json.dumps({'action': action, 'user_id': user_id, 'username': args.username}, ensure_ascii=False))
        return 0

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
            auth_issuer_password=cfg.POSTGRES_AUTH_ISSUER_PASSWORD,
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
            auth_issuer_password=cfg.POSTGRES_AUTH_ISSUER_PASSWORD,
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
