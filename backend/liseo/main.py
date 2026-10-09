"""HTTP API and static UI."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from liseo import __version__
from liseo.auth import clear_session, issue_session, passwords_match, require_origin, require_session
from liseo.config import ConfigError, get_settings
from liseo.service import ServiceError, account_status, activate_account, fulfill_acsm

log = logging.getLogger("liseo")


class _RedactFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [item for item in secrets if item]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[redacted]")
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class LoginBody(BaseModel):
    password: str


class ActivateBody(BaseModel):
    username: str
    password: str
    replace: bool = False


def create_app() -> FastAPI:
    app = FastAPI(title="Liseo", version=__version__, docs_url=None, redoc_url=None)
    try:
        settings = get_settings()
    except ConfigError as exc:
        @app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
        def not_configured(path: str) -> JSONResponse:
            return JSONResponse(status_code=500, content={"detail": "Le serveur n'est pas configuré."})

        log.error("configuration error: %s", exc.__class__.__name__)
        return app

    logging.getLogger().addFilter(_RedactFilter([settings.admin_password, settings.secret_key]))
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/api/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict[str, bool]:
        require_origin(request, settings)
        if not passwords_match(body.password, settings.admin_password):
            raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
        issue_session(response, settings)
        return {"ok": True}

    @app.post("/api/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        require_origin(request, settings)
        require_session(request, settings)
        clear_session(response, settings)
        return {"ok": True}

    @app.get("/api/status")
    def status(request: Request) -> dict[str, object]:
        require_session(request, settings)
        payload = account_status(settings)
        payload["version"] = __version__
        return payload

    @app.post("/api/account/activate")
    async def activate(body: ActivateBody, request: Request) -> dict[str, object]:
        require_origin(request, settings)
        require_session(request, settings)
        try:
            return await asyncio.to_thread(
                activate_account, settings, body.username, body.password, body.replace
            )
        except ServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/fulfill")
    async def fulfill(request: Request, file: UploadFile = File(...)) -> Response:
        require_origin(request, settings)
        require_session(request, settings)
        payload = await file.read()
        if len(payload) > 1_000_000:
            raise HTTPException(status_code=413, detail="Le fichier .acsm est trop volumineux.")
        try:
            data, info = await asyncio.to_thread(fulfill_acsm, settings, payload)
        except ServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        filename = _download_name(info.creator, info.title)
        encoded = quote(filename)
        return Response(
            content=data,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f"attachment; filename=\"book.epub\"; filename*=UTF-8''{encoded}",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    static_dir = _static_dir()
    if static_dir is not None:
        assets = static_dir / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Introuvable.")
            root = static_dir.resolve()
            candidate = (static_dir / path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return FileResponse(static_dir / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


def _download_name(creator: str, title: str) -> str:
    base = " - ".join(part.strip() for part in (creator, title) if part and part.strip())
    if not base:
        base = "livre"
    cleaned = "".join(char if char not in '\\/:*?"<>|\r\n' else "_" for char in base)
    cleaned = cleaned.strip().rstrip(".") or "livre"
    return f"{cleaned[:120]}.epub"


def _static_dir() -> Path | None:
    candidates = [
        Path("/app/static"),
        Path(__file__).resolve().parents[2] / "web" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


app = create_app()
