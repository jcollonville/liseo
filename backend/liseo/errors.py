"""Turn libgourou messages into short French errors. Never echo secrets."""

from __future__ import annotations

import re

_RESET = "E_ADEPT_RESET_PW_REQUIRED"


def translate_cli_error(output: str, password: str = "") -> str:
    text = output
    if password:
        text = text.replace(password, "")
    if _RESET in text:
        return (
            "Cet identifiant n'est plus accepté. Utilisez un identifiant ByteBooks : "
            "depuis le 23 juin 2026, un Adobe ID ne peut plus activer un nouvel appareil."
        )
    if "Anonymous activation is disabled" in text:
        return "L'activation anonyme est désactivée."
    code = _exception_code(text)
    if code == "0x1300":
        return "Identifiant ou mot de passe refusé."
    if "doesn't exists" in text and "activate" in text.lower():
        return "Aucun appareil activé. Activez d'abord le compte ByteBooks."
    if code:
        return f"L'outil interne a renvoyé le code {code}."
    return "L'opération a échoué."


def _exception_code(text: str) -> str | None:
    match = re.search(r"Exception code\s*:\s*(0x[0-9a-fA-F]+)", text)
    if not match:
        return None
    return match.group(1).lower()
