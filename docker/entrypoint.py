#!/usr/bin/env python3
"""Fix /data ownership, then drop root before serving."""

from __future__ import annotations

import os
import sys

UID = 1000


def _chown_tree(path: str) -> None:
    os.chown(path, UID, UID)
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            os.chown(os.path.join(dirpath, name), UID, UID)


def main() -> None:
    os.makedirs("/data/adept", exist_ok=True)
    if os.geteuid() == 0:
        _chown_tree("/data")
        os.setgroups([])
        os.setgid(UID)
        os.setuid(UID)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
