from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import sql
from sqlalchemy import Engine

from .credentials import validate_database_role_secret

RUNTIME_ROLE_READ_ONLY = {
    'cafeteria_app': 'off',
    'cafeteria_backup': 'on',
    'cafeteria_auth_issuer': 'off',
}


def _driver_connection(raw: Any) -> Any:
    connection = raw.driver_connection
    if connection is None:
        raise RuntimeError('Kein nativer Datenbanktreiber verbunden.')
    return connection


def _role_exists(cursor: Any, role_name: str) -> bool:
    return bool(
        cursor.execute(
            'SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)',
            (role_name,),
        ).fetchone()[0]
    )


def _set_role_attributes(
    cursor: Any,
    role_name: str,
    *,
    login: bool,
    password: str | None,
) -> None:
    action = 'ALTER ROLE' if _role_exists(cursor, role_name) else 'CREATE ROLE'
    password_clause = sql.SQL(' PASSWORD {}').format(sql.Literal(password)) if password else sql.SQL('')
    cursor.execute(
        sql.SQL(
            '{} {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT '
            "NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1 VALID UNTIL 'infinity'{}"
        ).format(
            sql.SQL(action),
            sql.Identifier(role_name),
            sql.SQL('LOGIN' if login else 'NOLOGIN'),
            password_clause,
        )
    )


def _reset_role_settings(cursor: Any, role_name: str) -> None:
    cursor.execute(sql.SQL('ALTER ROLE {} RESET ALL').format(sql.Identifier(role_name)))
    cursor.execute(
        sql.SQL('ALTER ROLE {} SET search_path = cafeteria, public').format(
            sql.Identifier(role_name)
        )
    )
    cursor.execute(
        sql.SQL("ALTER ROLE {} SET timezone = 'UTC'").format(sql.Identifier(role_name))
    )
    cursor.execute(
        sql.SQL('ALTER ROLE {} SET default_transaction_read_only = {}').format(
            sql.Identifier(role_name),
            sql.SQL(RUNTIME_ROLE_READ_ONLY[role_name]),
        )
    )


def _remove_memberships(cursor: Any, role_name: str) -> None:
    memberships = cursor.execute(
        '''
        SELECT granted.rolname, member.rolname
        FROM pg_auth_members membership
        JOIN pg_roles granted ON granted.oid=membership.roleid
        JOIN pg_roles member ON member.oid=membership.member
        WHERE granted.rolname=%s OR member.rolname=%s
        ''',
        (role_name, role_name),
    ).fetchall()
    for granted_role, member_role in memberships:
        cursor.execute(
            sql.SQL('REVOKE {} FROM {}').format(
                sql.Identifier(granted_role),
                sql.Identifier(member_role),
            )
        )


def terminate_role_sessions(cursor: Any, role_name: str) -> None:
    terminated = cursor.execute(
        '''
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE usename=%s AND pid <> pg_backend_pid()
        ''',
        (role_name,),
    ).fetchall()
    if any(not bool(row[0]) for row in terminated):
        raise RuntimeError(f'Aktive Sitzungen für {role_name} konnten nicht beendet werden.')
    for _ in range(20):
        cursor.execute('SELECT pg_stat_clear_snapshot()')
        remaining = cursor.execute(
            '''
            SELECT count(*)
            FROM pg_stat_activity
            WHERE usename=%s AND pid <> pg_backend_pid()
            ''',
            (role_name,),
        ).fetchone()[0]
        if not remaining:
            return
        cursor.execute('SELECT pg_sleep(0.05)')
    raise RuntimeError(f'Aktive Sitzungen für {role_name} bleiben nach Rotation bestehen.')


def provision_database_roles(
    engine: Engine,
    *,
    app_password: str,
    backup_password: str,
    auth_issuer_password: str,
    terminate_sessions: Callable[[Any, str], None] = terminate_role_sessions,
) -> None:
    credentials = (
        ('cafeteria_app', app_password),
        ('cafeteria_backup', backup_password),
        ('cafeteria_auth_issuer', auth_issuer_password),
    )
    for role_name, password in credentials:
        validate_database_role_secret(password, label=role_name)
    if len({password for _, password in credentials}) != len(credentials):
        raise RuntimeError('PostgreSQL-Rollen benötigen eigene, voneinander verschiedene Secrets.')

    raw = engine.raw_connection()
    try:
        connection = _driver_connection(raw)
        with connection.cursor() as cursor:
            for role_name, password in credentials[:2]:
                _set_role_attributes(cursor, role_name, login=True, password=password)
                _reset_role_settings(cursor, role_name)
                _remove_memberships(cursor, role_name)
            issuer_role = 'cafeteria_auth_issuer'
            _set_role_attributes(cursor, issuer_role, login=False, password=None)
            _reset_role_settings(cursor, issuer_role)
            _remove_memberships(cursor, issuer_role)
            connection.commit()

            try:
                terminate_sessions(cursor, issuer_role)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            _set_role_attributes(
                cursor,
                issuer_role,
                login=True,
                password=auth_issuer_password,
            )
            connection.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
