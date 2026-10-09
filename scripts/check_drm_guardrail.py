#!/usr/bin/env python3
"""Fail if a tree or image still contains DRM-removal tools or features.

Scans filenames and file contents. The needles live only in this script, which
is not copied into the runtime image.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

FORBIDDEN_FILENAMES = {
    "adept_remove",
    "adept_remove.cpp",
    "adept_remove.1",
}
FORBIDDEN_BLOBS = (
    b"export-private-key",
    b"--anonymous",
    b"removeDRM",
    b"removeEPubDRM",
    b"removePDFDRM",
    b"exportPrivateLicenseKey",
    b"decryptADEPTKey",
    b"adept_remove",
)


def scan_tree(root: Path) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return [f"missing path: {root}"]
    for path in root.rglob("*"):
        if not path.is_file() and not path.is_symlink():
            continue
        if path.name in FORBIDDEN_FILENAMES:
            hits.append(f"forbidden file: {path}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            hits.append(f"unreadable: {path}: {exc}")
            continue
        for needle in FORBIDDEN_BLOBS:
            if needle in data:
                hits.append(f"{path}: contains {needle.decode()}")
                break
    return hits


def scan_image(tag: str) -> list[str]:
    name = "liseo-guardrail-scan"
    subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)
    subprocess.check_call(["docker", "create", "--name", name, tag], stdout=subprocess.DEVNULL)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "image.tar"
            subprocess.check_call(["docker", "export", "-o", str(archive), name])
            return _scan_tar(archive)
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


def _scan_tar(archive: Path) -> list[str]:
    hits: list[str] = []
    with tarfile.open(archive) as tar:
        for member in tar:
            filename = Path(member.name).name
            if filename in FORBIDDEN_FILENAMES:
                hits.append(f"forbidden file: {member.name}")
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            for needle in FORBIDDEN_BLOBS:
                if needle in data:
                    hits.append(f"{member.name}: contains {needle.decode()}")
                    break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", default=[])
    parser.add_argument("--docker-image")
    args = parser.parse_args()
    hits: list[str] = []
    for root in args.root:
        hits.extend(scan_tree(root))
    if args.docker_image:
        hits.extend(scan_image(args.docker_image))
    if not args.root and not args.docker_image:
        parser.error("pass --root and/or --docker-image")
    if hits:
        print("DRM guardrail failed:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        return 1
    print("DRM guardrail passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
