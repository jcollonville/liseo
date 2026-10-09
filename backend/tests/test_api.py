import json
import os
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from liseo.config import get_settings
from liseo.crypto_store import fernet_from_secret, unseal_tree
from liseo.main import create_app

ORIGIN = {"origin": "http://localhost:8080"}
PASSWORD = "s3cret-bytebooks"
ADMIN = "test-admin-password"


def _encrypted_epub() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/rights.xml", "<rights xmlns='http://ns.adobe.com/adept'/>")
        archive.writestr(
            "META-INF/encryption.xml",
            "<encryption xmlns='urn:oasis:names:tc:opendocument:xmlns:container'/>",
        )
    return buffer.getvalue()


def _plain_epub() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OEBPS/chapter.xhtml", "PLAINTEXT-BOOK")
    return buffer.getvalue()


def _write_activate(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
report = Path(os.environ["MOCK_ARGV_LOG"])
report.write_text(json.dumps(sys.argv))
prompt = "Enter password for <user> : "
sys.stdout.write(prompt)
sys.stdout.flush()
password = sys.stdin.readline().rstrip("\\n")
Path(os.environ["MOCK_STDIN_LOG"]).write_text(password)
args = sys.argv[1:]
output = Path(args[args.index("-O") + 1])
output.mkdir(parents=True)
(output / "device.xml").write_text("<device/>")
(output / "activation.xml").write_text("<activation>PRIVATE-MARKER</activation>")
(output / "devicesalt").write_bytes(b"salt-bytes")
print("activated")
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_downloader(path: Path, plain: bool) -> None:
    body = _plain_epub() if plain else _encrypted_epub()
    path.write_text(
        f"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["MOCK_ARGV_LOG"]).write_text(json.dumps(sys.argv))
args = sys.argv[1:]
output = Path(args[args.index("-o") + 1])
output.write_bytes({body!r})
print("Created", output)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


@pytest.fixture
def client(tmp_path, monkeypatch):
    argv_log = tmp_path / "argv.json"
    stdin_log = tmp_path / "stdin.txt"
    activate = tmp_path / "adept_activate"
    download = tmp_path / "acsmdownloader"
    _write_activate(activate)
    _write_downloader(download, plain=False)
    monkeypatch.setenv("LISEO_ADMIN_PASSWORD", ADMIN)
    monkeypatch.setenv("LISEO_SECRET_KEY", "unit-test-secret")
    monkeypatch.setenv("LISEO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LISEO_ADEPT_ACTIVATE", str(activate))
    monkeypatch.setenv("LISEO_ACSM_DOWNLOADER", str(download))
    monkeypatch.setenv("LISEO_ALLOWED_OPERATORS", "acs4.edenlivres.fr")
    monkeypatch.setenv("LISEO_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("MOCK_ARGV_LOG", str(argv_log))
    monkeypatch.setenv("MOCK_STDIN_LOG", str(stdin_log))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _login(client: TestClient) -> None:
    response = client.post("/api/login", json={"password": ADMIN}, headers=ORIGIN)
    assert response.status_code == 200


def _acsm(host: str = "acs4.edenlivres.fr", expiration: str = "2026-12-01T18:00:00+01:00") -> bytes:
    return f"""<?xml version="1.0"?>
<fulfillmentToken fulfillmentType="loan" auth="user" xmlns="http://ns.adobe.com/adept"
    xmlns:dc="http://purl.org/dc/elements/1.1/">
  <operatorURL>http://{host}/fulfillment</operatorURL>
  <expiration>{expiration}</expiration>
  <resourceItemInfo><resourceItem><metadata>
    <dc:title>Plus grand que le ciel</dc:title>
    <dc:creator>Virginie Grimaldi</dc:creator>
    <dc:format>application/epub+zip</dc:format>
  </metadata></resourceItem></resourceItemInfo>
</fulfillmentToken>
""".encode()


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_requires_login(client):
    assert client.get("/api/status").status_code == 401
    _login(client)
    body = client.get("/api/status").json()
    assert body["activated"] is False


def test_activate_seals_files_and_hides_password(client, tmp_path, caplog):
    _login(client)
    with caplog.at_level("DEBUG"):
        response = client.post(
            "/api/account/activate",
            json={"username": "jean@example.com", "password": PASSWORD},
            headers=ORIGIN,
        )
    assert response.status_code == 200, response.text
    assert response.json()["activated"] is True
    assert response.json()["username"] == "jean@example.com"
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert PASSWORD not in argv
    assert "-p" not in argv
    assert (tmp_path / "stdin.txt").read_text() == PASSWORD
    sealed = (tmp_path / "data" / "adept" / "activation.xml.sealed").read_bytes()
    assert b"PRIVATE-MARKER" not in sealed
    restored = tmp_path / "restored"
    unseal_tree(tmp_path / "data" / "adept", restored, fernet_from_secret("unit-test-secret"))
    assert b"PRIVATE-MARKER" in (restored / "activation.xml").read_bytes()
    assert PASSWORD not in caplog.text
    assert "unit-test-secret" not in caplog.text


def test_fulfill_returns_encrypted_epub_only(client, tmp_path):
    _login(client)
    client.post(
        "/api/account/activate",
        json={"username": "jean@example.com", "password": PASSWORD},
        headers=ORIGIN,
    )
    response = client.post(
        "/api/fulfill",
        files={"file": ("loan.acsm", _acsm(), "application/vnd.adobe.adept+xml")},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/epub+zip")
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert "META-INF/rights.xml" in archive.namelist()
        assert "META-INF/encryption.xml" in archive.namelist()
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert "-D" in argv
    assert not (tmp_path / "data" / "adept").joinpath("activation.xml").exists()


def test_fulfill_rejects_plaintext_epub(client, tmp_path, monkeypatch):
    plain = tmp_path / "plain_downloader"
    _write_downloader(plain, plain=True)
    monkeypatch.setenv("LISEO_ACSM_DOWNLOADER", str(plain))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as local:
        local.post("/api/login", json={"password": ADMIN}, headers=ORIGIN)
        local.post(
            "/api/account/activate",
            json={"username": "jean@example.com", "password": PASSWORD},
            headers=ORIGIN,
        )
        response = local.post(
            "/api/fulfill",
            files={"file": ("loan.acsm", _acsm(), "application/vnd.adobe.adept+xml")},
            headers=ORIGIN,
        )
    assert response.status_code == 422
    assert b"PLAINTEXT-BOOK" not in response.content
    get_settings.cache_clear()


def test_unknown_operator_is_refused_before_download(client, tmp_path):
    _login(client)
    client.post(
        "/api/account/activate",
        json={"username": "jean@example.com", "password": PASSWORD},
        headers=ORIGIN,
    )
    (tmp_path / "argv.json").unlink(missing_ok=True)
    response = client.post(
        "/api/fulfill",
        files={"file": ("loan.acsm", _acsm(host="evil.example"), "application/octet-stream")},
        headers=ORIGIN,
    )
    assert response.status_code == 400
    assert "evil.example" in response.json()["detail"]
    assert not (tmp_path / "argv.json").exists() or "acsmdownloader" not in (tmp_path / "argv.json").read_text()


def test_login_rejects_bad_origin(client):
    response = client.post("/api/login", json={"password": ADMIN}, headers={"origin": "http://evil.example"})
    assert response.status_code == 403
