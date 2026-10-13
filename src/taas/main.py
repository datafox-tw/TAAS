from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .repository import DashboardRepository
from .scenarios import FUNDING_PRESETS, evaluate_scenarios
from .schemas import ScenarioRequest


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
STATIC_DIR = PACKAGE_DIR / "static"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "demo"


def data_directory() -> Path:
    return Path(os.getenv("TAAS_DATA_DIR", str(DEFAULT_DATA_DIR)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = DashboardRepository(data_directory())
    yield


app = FastAPI(
    title="TAAS 內科晨峰決策 API",
    version="0.1.0",
    description="公開交通資料重播與透明政策情境模型。",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1_000)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self'; "
        "font-src 'self'; object-src 'none'; base-uri 'self'"
    )
    return response


def repository(request: Request) -> DashboardRepository:
    return request.app.state.repository


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health(repo: DashboardRepository = Depends(repository)) -> dict:
    return {
        "status": "ok",
        "service": "taas-dashboard",
        "version": "0.1.0",
        "stations": len(repo.stations),
        "minutes": len(repo.times),
    }


@app.get("/api/meta")
def meta(repo: DashboardRepository = Depends(repository)) -> dict:
    payload = repo.metadata()
    payload["defaults"] = ScenarioRequest().model_dump()
    payload["funding_presets"] = FUNDING_PRESETS
    return payload


@app.get("/api/traffic/snapshot")
def traffic_snapshot(
    at: str | None = Query(default=None, description="Timestamp returned by /api/meta"),
    corridor: str = Query(default="all"),
    repo: DashboardRepository = Depends(repository),
) -> dict:
    selected_time = at or repo.times[60]
    try:
        return repo.snapshot(selected_time, corridor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/traffic/series")
def traffic_series(
    corridor: str = Query(default="all"),
    repo: DashboardRepository = Depends(repository),
) -> dict:
    try:
        return repo.traffic_series(corridor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demand/origins")
def demand_origins(
    limit: int = Query(default=12, ge=1, le=50),
    repo: DashboardRepository = Depends(repository),
) -> dict:
    return repo.demand_origins(limit)


@app.post("/api/scenarios/evaluate")
def scenarios_evaluate(
    scenario: ScenarioRequest,
    repo: DashboardRepository = Depends(repository),
) -> dict:
    try:
        baseline = repo.traffic_series(scenario.corridor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = evaluate_scenarios(baseline["series"], scenario)
    result["corridor"] = {"id": scenario.corridor, "label": baseline["corridor_label"]}
    result["baseline_warning"] = baseline["warning"]
    return result


def run() -> None:
    uvicorn.run(
        "taas.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("TAAS_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    run()
