"""REST + SSE API — ใช้แทน Streamlit สำหรับงาน agentic"""

from __future__ import annotations

import json
import threading
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from ..services.orchestrator import Orchestrator, RunNotFound
from ..services.store import RunStore
from .schemas import CreatedResponse, InvestigateRequest, ReviewRequest, RunResponse

TERMINAL = {"done", "failed", "cancelled"}
POLL_SECONDS = 0.4


def create_app(store: RunStore | None = None) -> FastAPI:
    import os

    if store is None:
        store = RunStore()
    os.environ.setdefault("OSINT_DB", str(store.path))
    orchestrator = Orchestrator(store)
    app = FastAPI(title="OSINT Lookup API", version="0.2.0")
    app.state.store = store
    app.state.orchestrator = orchestrator

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    def investigate(payload: InvestigateRequest) -> CreatedResponse:
        run_id = orchestrator.start(payload.target.strip(), payload.profile, payload.trusted)
        _run_in_background(run_id)
        return CreatedResponse(run_id=run_id)

    @app.get("/runs", response_model=list[RunResponse])
    def list_runs(limit: int = 50) -> list[dict]:
        return store.list_runs(limit)

    @app.get("/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str) -> dict:
        run = store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        return run

    @app.post("/runs/{run_id}/cancel", response_model=RunResponse)
    def cancel(run_id: str) -> dict:
        if not orchestrator.cancel(run_id):
            run = store.get_run(run_id)
            if not run:
                raise RunNotFound(run_id)
            return run
        return store.get_run(run_id)

    @app.post("/runs/{run_id}/resume", response_model=CreatedResponse)
    def resume(run_id: str) -> CreatedResponse:
        run = store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        store.set_status(run_id, "queued")
        _run_in_background(run_id)
        return CreatedResponse(run_id=run_id)

    @app.get("/runs/{run_id}/report")
    def report(run_id: str) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "markdown": store.get_report(run_id) or ""}

    @app.get("/runs/{run_id}/candidates")
    def candidates(run_id: str) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "candidates": store.list_candidates(run_id)}

    @app.post("/runs/{run_id}/review")
    def review(run_id: str, payload: ReviewRequest) -> dict:
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
    def findings(run_id: str) -> dict:
        if not store.get_run(run_id):
            raise RunNotFound(run_id)
        return {"run_id": run_id, "findings": store.list_findings(run_id)}

    @app.get("/runs/{run_id}/research-report")
    def research_report(run_id: str, format: str = "md"):
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
    def export(run_id: str) -> dict:
        data = store.to_dict(run_id)
        if not data:
            raise RunNotFound(run_id)
        return data

    @app.get("/runs/{run_id}/events")
    def events(run_id: str, after: int = 0) -> StreamingResponse:
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
