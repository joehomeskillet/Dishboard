"""Host-only password rotation; run explicitly after verified production deployment."""
from __future__ import annotations

import json
import os
import secrets
import stat

import pexpect

DIRECTORY = '/root/.dishboard'
PENDING = 'kueche.admin.pending-password'
FINAL = 'kueche.admin.initial-password'
USERNAME = 'kueche.admin'


def _private_directory() -> int:
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open('/root', flags)
    try:
        info = os.fstat(parent)
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError('Unsafe parent directory')
        try:
            os.mkdir('.dishboard', mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
        os.fsync(parent)
        directory = os.open('.dishboard', flags, dir_fd=parent)
    finally:
        os.close(parent)
    info = os.fstat(directory)
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        os.close(directory)
        raise RuntimeError('Unsafe credential directory')
    return directory


def _check_file(directory: int, name: str) -> os.stat_result | None:
    try:
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise RuntimeError('Unsafe credential file')
    return info


def _rotate(password: str) -> None:
    child = pexpect.spawn(
        'rtk', ['docker', 'compose', 'run', '--rm', '--no-deps', 'migrate',
                'python', '/app/manage.py', 'set-local-password',
                '--actor', USERNAME, '--username', USERNAME],
        cwd='/srv/dishboard/app/deployment', encoding='utf-8', codec_errors='replace',
        timeout=120, logfile=None,
    )
    try:
        for prompt in ('Lokales Passwort: ', 'Lokales Passwort wiederholen: '):
            child.expect_exact(prompt)
            if not child.waitnoecho(timeout=15):
                raise RuntimeError('Terminal echo is enabled')
            child.sendline(password)
        child.expect(pexpect.EOF)
        confirmed = False
        for line in child.before.splitlines():
            try:
                result = json.loads(line)
            except ValueError:
                continue
            if isinstance(result, dict) and set(result) == {'action', 'user_id', 'username'}:
                confirmed = (result['action'] == 'password_changed'
                             and result['username'] == USERNAME
                             and type(result['user_id']) is int and result['user_id'] > 0)
                if confirmed:
                    break
        child.close()
        if not confirmed or child.exitstatus != 0 or child.signalstatus is not None:
            raise RuntimeError('Rotation not confirmed')
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> int:
    directory = None
    try:
        directory = _private_directory()
        _check_file(directory, FINAL)
        password = 'Aa1!' + secrets.token_urlsafe(48)
        descriptor = os.open(
            PENDING, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600, dir_fd=directory,
        )
        with os.fdopen(descriptor, 'w', encoding='utf-8') as pending:
            original = os.fstat(pending.fileno())
            pending.write(password + '\n')
            pending.flush()
            os.fsync(pending.fileno())
        _check_file(directory, PENDING)
        os.fsync(directory)
        _rotate(password)
        current = _check_file(directory, PENDING)
        if current is None or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
            raise RuntimeError('Pending credential replaced')
        _check_file(directory, FINAL)
        os.replace(PENDING, FINAL, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
        print('action=password_changed; protected credential promoted')
        return 0
    except (Exception, KeyboardInterrupt):
        # Pexpect exception text can contain credentials; never print its buffers or traceback.
        print(f'Rotation not confirmed. Do not retry automatically. Check protected credentials in {DIRECTORY}.')
        return 1
    finally:
        if directory is not None:
            os.close(directory)


if __name__ == '__main__':
    raise SystemExit(main())
