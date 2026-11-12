"""REST + SSE API — ใช้แทน Streamlit สำหรับงาน agentic"""

from __future__ import annotations

import json
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .. import access, auth
from ..services.orchestrator import Orchestrator, RunNotFound
from ..services.store import RunStore
from .schemas import (
    CreatedResponse,
    InvestigateRequest,
    LoginRequest,
    PivotRequest,
    ReviewRequest,
    RunResponse,
    TokenResponse,
    UserOut,
)

TERMINAL = {"done", "failed", "cancelled"}
POLL_SECONDS = 0.4


DEMO_USER = {"username": "demo", "name": "demo", "role": "admin", "unit": "-"}


def create_app(store: RunStore | None = None, auth_required: bool = True) -> FastAPI:
    import os

    if store is None:
        store = RunStore()
    os.environ.setdefault("OSINT_DB", str(store.path))
    orchestrator = Orchestrator(store)
    app = FastAPI(title="OSINT Lookup API", version="0.2.0")
    app.state.store = store
    app.state.orchestrator = orchestrator
    app.state.auth_required = auth_required

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def current_user(
        request: Request,
        authorization: str | None = Header(default=None),
        token: str | None = Query(default=None),
    ) -> dict:
        if not app.state.auth_required:
            return DEMO_USER
        bearer = ""
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        user = auth.verify_token(bearer or token or "")
        if not user:
            raise HTTPException(
                status_code=401,
                detail={"code": "unauthorized", "message": "ต้องเข้าสู่ระบบก่อน"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    def require(permission: str):
        def dependency(user: dict = Depends(current_user)) -> dict:
            if not auth.has_permission(user, permission):
                raise HTTPException(
                    status_code=403,
                    detail={"code": "forbidden", "message": f"บทบาท {user.get('role')} ไม่มีสิทธิ์ {permission}"},
                )
            return user

        return dependency

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)

    @app.post("/auth/login", response_model=TokenResponse)
    def login(payload: LoginRequest) -> dict:
        user = auth.authenticate(payload.username, payload.password)
        if not user:
            access.audit("login_failed", {"name": payload.username})
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_credentials", "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
            )
        access.audit("login", user)
        return {
            "access_token": auth.issue_token(user),
            "expires_in": auth.TOKEN_TTL,
            "user": user,
        }

    @app.get("/auth/me", response_model=UserOut)
    def me(user: dict = Depends(current_user)) -> dict:
        return user

    @app.post("/auth/logout")
    def logout(user: dict = Depends(current_user)) -> dict:
        access.audit("logout", user)
        return {"ok": True}

    @app.get("/auth/users", response_model=list[UserOut])
    def users(user: dict = Depends(require("manage_users"))) -> list[dict]:
        return auth.list_public_users()

    @app.exception_handler(RunNotFound)
    async def _not_found(_request: Request, exc: RunNotFound):
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "run_not_found", "message": f"ไม่พบ run {exc}"}},
        )

    def _run_in_background(run_id: str) -> None:
        threading.Thread(target=orchestrator.run, args=(run_id,), daemon=True).start()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/investigate", response_model=CreatedResponse, status_code=202)
    def investigate(payload: InvestigateRequest, user: dict = Depends(require("investigate"))) -> CreatedResponse:
        run_id = orchestrator.start(payload.target.strip(), payload.profile, payload.trusted)
        _run_in_background(run_id)
        return CreatedResponse(run_id=run_id)

    @app.get("/runs", response_model=list[RunResponse])
    def list_runs(limit: int = 50, user: dict = Depends(require("read"))) -> list[dict]:
        return store.list_runs(limit)

    @app.get("/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str, user: dict = Depends(require("read"))) -> dict:
        run = store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        return run

    @app.post("/runs/{run_id}/cancel", response_model=RunResponse)
    def cancel(run_id: str, user: dict = Depends(require("cancel"))) -> dict:
        if not orchestrator.cancel(run_id):
            run = store.get_run(run_id)
            if not run:
                raise RunNotFound(run_id)
            return run
        return store.get_run(run_id)

    @app.post("/runs/{run_id}/resume", response_model=CreatedResponse)
    def resume(run_id: str, user: dict = Depends(require("investigate"))) -> CreatedResponse:
        run = store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        store.set_status(run_id, "queued")
        _run_in_background(run_id)
        return CreatedResponse(run_id=run_id)

    @app.get("/runs/{run_id}/analysis")
    def analysis(run_id: str, user: dict = Depends(require("read"))) -> dict:
        from ..profiling import analysis_view

        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return analysis_view.build(store, run_id)

    @app.post("/runs/{run_id}/pivot", response_model=CreatedResponse, status_code=202)
    def pivot(run_id: str, payload: PivotRequest, user: dict = Depends(require("investigate"))) -> CreatedResponse:
        parent = store.get_run(run_id)
        if not parent:
            raise RunNotFound(run_id)
        child = orchestrator.start(
            payload.identifier.strip(), payload.profile, payload.trusted, parent_run_id=run_id
        )
        _run_in_background(child)
        return CreatedResponse(run_id=child)

    @app.get("/runs/{run_id}/report")
    def report(run_id: str, user: dict = Depends(require("read"))) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "markdown": store.get_report(run_id) or ""}

    @app.get("/runs/{run_id}/candidates")
    def candidates(run_id: str, user: dict = Depends(require("read"))) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "candidates": store.list_candidates(run_id)}

    @app.post("/runs/{run_id}/review")
    def review(run_id: str, payload: ReviewRequest, user: dict = Depends(require("review"))) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        decided = store.decide_candidate(run_id, payload.candidate_id, payload.action)
        if decided is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "candidate_not_found", "message": payload.candidate_id}},
            )
        return decided

    @app.get("/runs/{run_id}/findings")
    def findings(run_id: str, user: dict = Depends(require("read"))) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "findings": store.list_findings(run_id)}

    @app.get("/runs/{run_id}/research-report")
    def research_report(run_id: str, format: str = "md", user: dict = Depends(require("read"))):
        import tempfile

        from fastapi.responses import FileResponse

        from ..profiling import profile_resolver
        from ..profiling import research_report as builder

        run = store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        artifacts = store.list_artifacts(run_id)
        entities = profile_resolver.extract_entities(artifacts)
        profiles = profile_resolver.resolve_profiles(artifacts, entities)
        markdown = builder.build_markdown(run, artifacts, store.list_findings(run_id), profiles, entities)
        if format == "docx":
            from pathlib import Path

            path = builder.to_docx(markdown, Path(tempfile.gettempdir()) / f"research_{run_id}.docx")
            return FileResponse(
                path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=f"research_{run_id}.docx",
            )
        return {"run_id": run_id, "markdown": markdown}

    @app.get("/runs/{run_id}/export")
    def export(run_id: str, user: dict = Depends(require("export"))) -> dict:
        data = store.to_dict(run_id)
        if not data:
            raise RunNotFound(run_id)
        return data

    @app.get("/runs/{run_id}/events")
    def events(run_id: str, after: int = 0, user: dict = Depends(require("read"))) -> StreamingResponse:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)

        def stream():
            cursor = after
            idle = 0.0
            while True:
                for event in store.list_events(run_id, cursor):
                    cursor = event["seq"]
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                run = store.get_run(run_id)
                if run and run["status"] in TERMINAL and not store.list_events(run_id, cursor):
                    yield "event: close\ndata: {}\n\n"
                    return
                idle += POLL_SECONDS
                if idle >= 15:
                    yield ": keepalive\n\n"
                    idle = 0.0
                time.sleep(POLL_SECONDS)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
