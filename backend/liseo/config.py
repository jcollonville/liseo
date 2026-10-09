"""Process configuration. Secrets come from the environment and are never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    admin_password: str
    secret_key: str
    data_dir: Path
    allowed_operators: tuple[str, ...]
    public_url: str
    activate_bin: str
    download_bin: str
    command_timeout: int
    cookie_secure: bool

    @property
    def adept_dir(self) -> Path:
        return self.data_dir / "adept"

    @property
    def allowed_origins(self) -> set[str]:
        origins = {
            self.public_url.rstrip("/"),
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        }
        return {item for item in origins if item}


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


@lru_cache
def get_settings() -> Settings:
    public_url = os.environ.get("LISEO_PUBLIC_URL", "http://localhost:8080").strip()
    operators = tuple(
        host.strip().lower()
        for host in os.environ.get("LISEO_ALLOWED_OPERATORS", "acs4.edenlivres.fr").split(",")
        if host.strip()
    )
    timeout = int(os.environ.get("LISEO_COMMAND_TIMEOUT", "180"))
    return Settings(
        admin_password=_required("LISEO_ADMIN_PASSWORD"),
        secret_key=_required("LISEO_SECRET_KEY"),
        data_dir=Path(os.environ.get("LISEO_DATA_DIR", "/data")),
        allowed_operators=operators,
        public_url=public_url.rstrip("/"),
        activate_bin=os.environ.get("LISEO_ADEPT_ACTIVATE", "/usr/local/bin/adept_activate"),
        download_bin=os.environ.get("LISEO_ACSM_DOWNLOADER", "/usr/local/bin/acsmdownloader"),
        command_timeout=timeout,
        cookie_secure=public_url.lower().startswith("https://"),
    )
