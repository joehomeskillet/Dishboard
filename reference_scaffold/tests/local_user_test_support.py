"""Create fixture identities through the same versioned issuer as the CLI."""
from __future__ import annotations

from sqlalchemy import Engine, text

from cafeteria.auth.local_users import create_local_user, load_local_command_context


def provision_local_fixture(issuer_engine: Engine, reader_engine: Engine, *,
                            actor_identifier: str, username: str, display_name: str,
                            password: str, roles: list[str]) -> int:
    actor = load_local_command_context(issuer_engine, actor_identifier=actor_identifier).actor
    result = create_local_user(issuer_engine, actor=actor, username=username,
                               display_name=display_name, password=password, roles=tuple(roles))
    with reader_engine.connect() as connection:
        return int(connection.execute(text('SELECT id FROM cafeteria.users WHERE public_id=:id'),
                                      {'id': result.public_id}).scalar_one())
