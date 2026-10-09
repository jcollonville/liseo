"""Refuse to serve a download that is not still an encrypted EPUB."""

from __future__ import annotations

import zipfile
from pathlib import Path


class EpubGuardError(ValueError):
    pass


def require_encrypted_epub(path: Path) -> None:
    """A fulfilled loan must still contain Adobe rights and encryption metadata.

    Liseo never decrypts the book. If those entries are missing, the file is
    discarded and nothing is returned to the browser.
    """
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise EpubGuardError(
            "Le fichier obtenu n'est pas un EPUB. Rien n'a été envoyé."
        )
    with zipfile.ZipFile(path) as archive:
        names = {item.replace("\\", "/") for item in archive.namelist()}
        if "META-INF/rights.xml" not in names or "META-INF/encryption.xml" not in names:
            raise EpubGuardError(
                "Le fichier obtenu n'est pas un EPUB chiffré "
                "(META-INF/rights.xml ou META-INF/encryption.xml absent). Rien n'a été envoyé."
            )
        rights = archive.read("META-INF/rights.xml")
        encryption = archive.read("META-INF/encryption.xml")
    if b"rights" not in rights.lower() or b"encryption" not in encryption.lower():
        raise EpubGuardError(
            "Les métadonnées de protection sont illisibles. Rien n'a été envoyé."
        )
