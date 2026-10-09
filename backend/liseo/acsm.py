"""Parse an Adobe ACSM fulfillment token without contacting the operator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from defusedxml import ElementTree


class AcsmError(ValueError):
    pass


@dataclass(frozen=True)
class AcsmInfo:
    fulfillment_type: str
    auth: str
    operator_url: str
    operator_host: str
    transaction: str
    expiration: datetime | None
    title: str
    creator: str
    format: str
    display_until: datetime | None

    def expired(self, now: datetime | None = None) -> bool:
        if self.expiration is None:
            return False
        current = now or datetime.now(timezone.utc)
        expiration = self.expiration
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return current > expiration


def parse_acsm(payload: bytes) -> AcsmInfo:
    if len(payload) > 1_000_000:
        raise AcsmError("Le fichier .acsm est trop volumineux.")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise AcsmError("Le fichier .acsm contient une structure XML refusée.")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise AcsmError("Le fichier .acsm n'est pas un XML lisible.") from exc

    values: dict[str, str] = {}
    for element in root.iter():
        name = _local(element.tag)
        text = "".join(element.itertext()).strip()
        if text and name not in values:
            values[name] = text

    operator_url = values.get("operatorURL", "").strip()
    host = _operator_host(operator_url)
    return AcsmInfo(
        fulfillment_type=(root.attrib.get("fulfillmentType") or "").strip(),
        auth=(root.attrib.get("auth") or "").strip(),
        operator_url=operator_url,
        operator_host=host,
        transaction=values.get("transaction", ""),
        expiration=_parse_time(values.get("expiration", "")),
        title=values.get("title", ""),
        creator=values.get("creator", ""),
        format=values.get("format", ""),
        display_until=_parse_time(values.get("until", "")),
    )


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _operator_host(url: str) -> str:
    if not url:
        raise AcsmError("Le fichier .acsm ne contient pas d'operatorURL.")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise AcsmError("L'adresse de l'opérateur n'est pas utilisable.")
    if parts.username or parts.password:
        raise AcsmError("L'adresse de l'opérateur n'est pas utilisable.")
    return parts.hostname.lower()


def _parse_time(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
