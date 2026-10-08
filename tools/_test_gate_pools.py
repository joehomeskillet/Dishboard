"""Loopback-only disposable pool validation, port discovery and process locks."""
from __future__ import annotations

import fcntl
import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

LOOPBACK = {'localhost', '127.0.0.1', '::1'}


def validate_database_url(value: str) -> None:
    try:
        url = urlsplit(value)
        safe = (url.scheme in {'postgresql', 'postgres', 'postgresql+psycopg', 'postgresql+psycopg2'}
                and url.hostname in LOOPBACK and 'test' in unquote(url.path).lower()
                and not url.query and not url.fragment and bool(url.port or 5432))
    except ValueError:
        safe = False
    if not safe:
        raise ValueError('database must be a loopback PostgreSQL test database without URL overrides')


def read_pool_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        key, separator, raw = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            raise ValueError(f'pool env line {number}: expected literal KEY=value')
        # Never source shell files. Expansions and command substitution are unsupported.
        if '$' in raw or '`' in raw:
            raise ValueError(f'pool env line {number}: shell expansion is forbidden')
        fields = shlex.split(raw, comments=True, posix=True)
        if len(fields) > 1:
            raise ValueError(f'pool env line {number}: value must be quoted')
        if key in values:
            raise ValueError(f'pool env line {number}: duplicate key')
        values[key] = fields[0] if fields else ''
    return values


def command(args: list[str]) -> str:
    for _ in range(2):
        result = subprocess.run(['rtk', *args], capture_output=True, text=True, shell=False, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip()
    raise ValueError(f'{args[0]} failed twice during pool preflight')


def published_port(container: str, port: int) -> int:
    output = command(['docker', 'port', container, f'{port}/tcp'])
    ports = {line.rsplit(':', 1)[-1] for line in output.splitlines() if line.strip()}
    if len(ports) != 1 or not next(iter(ports)).isdigit():
        raise ValueError('ambiguous or missing published container port')
    value = int(next(iter(ports)))
    if not 1 <= value <= 65535:
        raise ValueError('invalid published port')
    return value


def with_port(value: str, port: int) -> str:
    url = urlsplit(value)
    credentials, separator, _ = url.netloc.rpartition('@')
    authority = (credentials + separator if separator else '') + f'127.0.0.1:{port}'
    return urlunsplit((url.scheme, authority, url.path, url.query, url.fragment))


@dataclass
class Pool:
    name: str
    env: dict[str, str]
    resources: tuple[str, str]


def load_pool(path: Path) -> Pool:
    values = read_pool_env(path)
    url = values.get('TEST_DATABASE_URL', '')
    validate_database_url(url)
    container = values.get('TEST_DATABASE_CONTAINER', '')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', container) or 'test' not in container.lower():
        raise ValueError('pool requires a named test container')
    redis_url = values.get('TEST_REDIS_URL', '')
    redis = urlsplit(redis_url)
    if redis.scheme != 'redis' or redis.hostname not in LOOPBACK or redis.query or redis.fragment:
        raise ValueError('Redis must use loopback without URL overrides')
    redis_container = values.get('TEST_REDIS_CONTAINER', container.removesuffix('-pg16') + '-redis')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', redis_container) or 'test' not in redis_container.lower():
        raise ValueError('pool requires a named test Redis container')
    pg_port = published_port(container, 5432)
    redis_port = published_port(redis_container, 6379)
    values['TEST_DATABASE_URL'] = with_port(url, pg_port)
    values['TEST_REDIS_URL'] = with_port(redis_url, redis_port)
    env = os.environ.copy()
    env.update(values)
    # Reject inherited production connections before any pytest module is imported.
    for key, value in env.items():
        if key.endswith('DATABASE_URL') and value:
            validate_database_url(value)
        if key.endswith('REDIS_URL') and value and urlsplit(value).hostname not in LOOPBACK:
            raise ValueError('inherited Redis URL is not loopback')
    # PostgreSQL roles are cluster-wide, even when database names differ.
    return Pool(path.stem, env, (f'pg:127.0.0.1:{pg_port}', f'redis:127.0.0.1:{redis_port}'))


def check_existing_pytest(pool: Pool) -> None:
    result = subprocess.run(['rtk', 'pgrep', '-f', pool.name], capture_output=True,
                            text=True, shell=False, timeout=10)
    if result.returncode not in (0, 1):
        raise ValueError('cannot inspect pool processes')
    candidates = {int(x) for x in result.stdout.split() if x.isdigit()}
    processes: dict[int, tuple[int, list[str]]] = {}
    for path in Path('/proc').glob('[0-9]*'):
        try:
            arguments = (path / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            parent = int((path / 'stat').read_text().rsplit(')', 1)[1].split()[1])
            processes[int(path.name)] = (parent, arguments)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    for pid in candidates:
        arguments = processes.get(pid, (0, []))[1]
        if 'pytest' in arguments and '--gate-pool-name' in arguments:
            index = arguments.index('--gate-pool-name')
            if arguments[index + 1:index + 2] == [pool.name]:
                raise ValueError(f'pool {pool.name} has an existing pytest process')
        # pgrep also finds agent prompts; only gate wrappers own a pool this way.
        if not any(Path(arg).name in {'gate.sh', 'poolrun.sh'} for arg in arguments):
            continue
        for child, (_, args) in processes.items():
            if 'pytest' not in args and not any(Path(arg).name == 'pytest' for arg in args):
                continue
            ancestor = child
            while ancestor in processes and ancestor > 1:
                if ancestor == pid:
                    raise ValueError(f'pool {pool.name} has an existing pytest process')
                ancestor = processes[ancestor][0]


def lock_pools(pools: list[Pool], stack: ExitStack) -> tuple[int, ...]:
    resources = [resource for pool in pools for resource in pool.resources]
    if len(resources) != len(set(resources)):
        raise ValueError('pool collision: duplicate database or Redis endpoint')
    directory = Path(tempfile.gettempdir()) / 'dishboard-test-gate-locks'
    directory.mkdir(mode=0o700, exist_ok=True)
    descriptors = []
    for resource in sorted(resources):
        name = hashlib.sha256(resource.encode()).hexdigest()
        handle = stack.enter_context((directory / name).open('a'))
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('pool already leased by another test gate') from exc
        descriptors.append(handle.fileno())
    return tuple(descriptors)


def enough_memory() -> bool:
    output = command(['free', '-g'])
    row = next((line.split() for line in output.splitlines() if line.startswith('Mem:')), [])
    if not row or not row[-1].isdigit():
        raise ValueError('cannot determine available memory')
    return int(row[-1]) >= 30
