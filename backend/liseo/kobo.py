"""Detect a Kobo volume from a directory tree.

The browser does the same checks with the File System Access API. This module
is the tested reference for a folder on disk (unit tests, fake volumes).
"""

from __future__ import annotations

import json
from pathlib import Path

_MODELS_PATH = Path(__file__).resolve().parents[2] / "shared" / "kobo_models.json"
BOOK_SUFFIXES = (".epub", ".pdf")
_SKIP_DIRS = {".kobo", ".adobe-digital-editions", ".kobo-images"}


def model_names() -> dict[str, str]:
    if not _MODELS_PATH.is_file():
        return {}
    data = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in data.items()}


def parse_version(text: str) -> dict[str, str]:
    """Parse `.kobo/version`.

    Calibre reads this CSV as: field 0 serial, field 2 firmware, last field
    model id (`00000000-0000-0000-0000-000000000376`). The last three digits
    identify the model.
    """
    fields = [part.strip() for part in text.strip().split(",")]
    serial = fields[0] if fields else ""
    firmware = fields[2] if len(fields) > 2 else ""
    model_id = fields[-1] if len(fields) > 1 else ""
    digits = "".join(char for char in model_id if char.isdigit())
    code = digits[-3:] if len(digits) >= 3 else ""
    names = model_names()
    if code and code in names:
        model_name = names[code]
    elif code:
        model_name = f"Kobo (code {code})"
    else:
        model_name = "Kobo"
    return {
        "serial": serial,
        "firmware": firmware,
        "model_id": model_id,
        "model_code": code,
        "model_name": model_name,
    }


def list_books(root: Path) -> list[dict[str, str]]:
    books: list[dict[str, str]] = []
    if not root.is_dir():
        return books
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS or part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        name = path.name
        if name.startswith("."):
            continue
        lower = name.lower()
        if lower.endswith(BOOK_SUFFIXES):
            books.append(
                {
                    "name": name,
                    "relative_path": path.relative_to(root).as_posix(),
                }
            )
    books.sort(key=lambda item: item["relative_path"].lower())
    return books


def inspect_kobo(root: Path) -> dict[str, object]:
    kobo_dir = root / ".kobo"
    if not kobo_dir.is_dir():
        return {
            "is_kobo": False,
            "error": "Ce dossier ne ressemble pas à une Kobo : le dossier .kobo est introuvable.",
        }
    version_path = kobo_dir / "version"
    if not version_path.is_file():
        return {
            "is_kobo": True,
            "error": "Kobo détectée, mais le fichier .kobo/version est introuvable.",
            "authorized": (root / ".adobe-digital-editions" / "activation.xml").is_file(),
            "books": [],
            "book_count": 0,
        }
    info = parse_version(version_path.read_text(encoding="utf-8", errors="replace"))
    books = list_books(root)
    authorized = (root / ".adobe-digital-editions" / "activation.xml").is_file()
    return {
        "is_kobo": True,
        "error": None,
        "authorized": authorized,
        "books": books,
        "book_count": len(books),
        **info,
    }
