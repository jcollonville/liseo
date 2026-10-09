"""Account activation and ACSM fulfillment. One operation at a time."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from liseo.acsm import AcsmError, AcsmInfo, parse_acsm
from liseo.config import Settings
from liseo.crypto_store import fernet_from_secret, has_activation, seal_tree, unseal_tree, wipe_tree
from liseo.epub_guard import EpubGuardError, require_encrypted_epub
from liseo.errors import translate_cli_error
from liseo.gourou import GourouError, GourouTimeout, run_command

_LOCK = threading.Lock()


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def account_status(settings: Settings) -> dict[str, object]:
    account = _read_account(settings)
    return {
        "activated": has_activation(settings.adept_dir) and account is not None,
        "username": None if account is None else account.get("username"),
        "activated_at": None if account is None else account.get("activated_at"),
    }


def activate_account(settings: Settings, username: str, password: str, replace: bool) -> dict[str, object]:
    username = username.strip()
    if not username or username.startswith("-") or any(char in username for char in "\r\n\x00"):
        raise ServiceError("Indiquez un identifiant ByteBooks valide.", 400)
    if not password:
        raise ServiceError("Indiquez le mot de passe du compte ByteBooks.", 400)
    if has_activation(settings.adept_dir) and not replace:
        raise ServiceError(
            "Un appareil est déjà activé dans ce volume. "
            "Le remplacer consomme un emplacement supplémentaire sur le compte.",
            409,
        )
    binary = Path(settings.activate_bin)
    if not binary.is_file():
        raise ServiceError("L'outil d'activation est absent de cette installation.", 500)

    with _LOCK:
        temp = Path(tempfile.mkdtemp(prefix="liseo-activate-"))
        output = temp / "device"
        try:
            os.chmod(temp, 0o700)
            try:
                run_command(
                    [str(binary), "-u", username, "-O", str(output), "-r"],
                    cwd=temp,
                    timeout=min(settings.command_timeout, 120),
                    password=password,
                )
            except GourouTimeout as exc:
                raise ServiceError(str(exc), 504) from exc
            except GourouError as exc:
                raise ServiceError(translate_cli_error(exc.output, password), 400) from exc
            required = [output / "activation.xml", output / "device.xml", output / "devicesalt"]
            if not all(path.is_file() for path in required):
                raise ServiceError("L'activation n'a pas produit les fichiers attendus.", 500)
            settings.adept_dir.parent.mkdir(parents=True, exist_ok=True)
            seal_tree(output, settings.adept_dir, fernet_from_secret(settings.secret_key))
            _write_account(settings, username)
        finally:
            wipe_tree(temp)
            password = ""
    return account_status(settings)


def fulfill_acsm(settings: Settings, payload: bytes) -> tuple[bytes, AcsmInfo]:
    try:
        info = parse_acsm(payload)
    except AcsmError as exc:
        raise ServiceError(str(exc), 400) from exc
    if info.operator_host not in settings.allowed_operators:
        raise ServiceError(
            f"L'opérateur « {info.operator_host} » n'est pas dans la liste autorisée.",
            400,
        )
    if info.expired():
        raise ServiceError("Le jeton .acsm a expiré. Rien n'a été demandé à l'opérateur.", 400)
    if info.format and "epub" not in info.format.lower():
        raise ServiceError(
            "Ce prototype ne récupère que les EPUB. Le fichier annoncé n'est pas un EPUB.",
            400,
        )
    if not has_activation(settings.adept_dir):
        raise ServiceError("Activez d'abord le compte ByteBooks.", 409)
    binary = Path(settings.download_bin)
    if not binary.is_file():
        raise ServiceError("L'outil de récupération est absent de cette installation.", 500)

    with _LOCK:
        temp = Path(tempfile.mkdtemp(prefix="liseo-fulfill-"))
        adept = temp / "adept"
        acsm_path = temp / "loan.acsm"
        output = temp / "loan.epub"
        try:
            os.chmod(temp, 0o700)
            try:
                unseal_tree(settings.adept_dir, adept, fernet_from_secret(settings.secret_key))
            except (FileNotFoundError, ValueError) as exc:
                raise ServiceError("Les données d'activation sont illisibles.", 500) from exc
            acsm_path.write_bytes(payload)
            os.chmod(acsm_path, 0o600)
            try:
                run_command(
                    [str(binary), "-D", str(adept), "-o", str(output), str(acsm_path)],
                    cwd=temp,
                    timeout=settings.command_timeout,
                )
            except GourouTimeout as exc:
                raise ServiceError(str(exc), 504) from exc
            except GourouError as exc:
                raise ServiceError(translate_cli_error(exc.output), 502) from exc
            try:
                require_encrypted_epub(output)
            except EpubGuardError as exc:
                raise ServiceError(str(exc), 422) from exc
            data = output.read_bytes()
            seal_tree(adept, settings.adept_dir, fernet_from_secret(settings.secret_key))
            return data, info
        finally:
            wipe_tree(temp)


def _account_path(settings: Settings) -> Path:
    return settings.data_dir / "account.json"


def _read_account(settings: Settings) -> dict[str, str] | None:
    path = _account_path(settings)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {"username": str(data.get("username") or ""), "activated_at": str(data.get("activated_at") or "")}


def _write_account(settings: Settings, username: str) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "username": username,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _account_path(settings)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)
