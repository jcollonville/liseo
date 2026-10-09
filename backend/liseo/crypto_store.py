"""Encrypt activation files at rest. Plaintext exists only in a temporary directory."""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def fernet_from_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _wipe_file(path: Path) -> None:
    if not path.is_file():
        return
    size = path.stat().st_size
    with path.open("r+b") as handle:
        handle.write(b"\0" * size)
        handle.flush()
        os.fsync(handle.fileno())
    path.unlink()


def wipe_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            _wipe_file(child)
        elif child.is_dir():
            child.rmdir()
    if path.exists():
        path.rmdir()


def seal_tree(source: Path, dest: Path, fernet: Fernet) -> None:
    """Replace dest with encrypted copies of every file under source."""
    if dest.exists():
        wipe_tree(dest)
    dest.mkdir(parents=True, mode=0o700)
    os.chmod(dest, 0o700)
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        target = dest / f"{relative}.sealed"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fernet.encrypt(path.read_bytes()))
        os.chmod(target, 0o600)


def unseal_tree(source: Path, dest: Path, fernet: Fernet) -> None:
    dest.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(dest, 0o700)
    found = False
    for path in source.rglob("*.sealed"):
        if not path.is_file():
            continue
        found = True
        relative = path.relative_to(source).as_posix()[: -len(".sealed")]
        target = dest / relative
        if not _is_inside(dest, target):
            raise ValueError("sealed path escapes the activation directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = fernet.decrypt(path.read_bytes())
        except InvalidToken as exc:
            raise ValueError("activation data cannot be decrypted") from exc
        target.write_bytes(data)
        os.chmod(target, 0o600)
    if not found:
        raise FileNotFoundError("no sealed activation files")


def has_activation(adept_dir: Path) -> bool:
    return (adept_dir / "activation.xml.sealed").is_file() and (adept_dir / "device.xml.sealed").is_file()


def _is_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def copy_private(source: Path, dest: Path) -> None:
    """Copy a directory tree and mark files readable only by the owner."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, mode=0o700)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = dest / relative
        if path.is_dir():
            target.mkdir(mode=0o700, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            os.chmod(target, 0o600)
