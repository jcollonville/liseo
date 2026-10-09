"""Run the restricted libgourou tools. The password is written to a pty, never to argv."""

from __future__ import annotations

import os
import select
import subprocess
import termios
import time
from pathlib import Path


class GourouError(RuntimeError):
    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.output = output


class GourouTimeout(GourouError):
    pass


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout: float,
    password: str | None = None,
) -> str:
    if any(arg == "-p" or arg.startswith("--password") for arg in argv):
        raise GourouError("Refusing to pass a password on the command line.")
    master, slave = os.openpty()
    if password is not None:
        attrs = termios.tcgetattr(slave)
        attrs[3] = attrs[3] & ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
    try:
        proc = subprocess.Popen(
            argv,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=str(cwd),
            close_fds=True,
        )
    except FileNotFoundError as exc:
        os.close(master)
        os.close(slave)
        raise GourouError("Les outils internes sont absents de cette installation.") from exc
    os.close(slave)
    os.set_blocking(master, False)
    chunks: list[bytes] = []
    sent = password is None
    secret = password.encode("utf-8") if password else b""
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=5)
                raise GourouTimeout("L'opération a dépassé le délai imparti.")
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    data = os.read(master, 8192)
                except OSError:
                    data = b""
                if data:
                    chunks.append(data)
                    if not sent and b"password" in b"".join(chunks).lower():
                        _write_all(master, secret + b"\n")
                        sent = True
            if proc.poll() is not None:
                while True:
                    try:
                        data = os.read(master, 8192)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                break
    finally:
        os.close(master)
        secret = b""
    output = b"".join(chunks)
    if password:
        output = output.replace(password.encode("utf-8"), b"")
    text = output.decode("utf-8", errors="replace")
    code = proc.returncode if proc.returncode is not None else 1
    if code != 0:
        raise GourouError("command failed", text)
    return text


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        try:
            written = os.write(fd, view)
        except BlockingIOError:
            select.select([], [fd], [], 1)
            continue
        view = view[written:]
