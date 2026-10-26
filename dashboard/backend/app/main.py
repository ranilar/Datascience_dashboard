import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import scoring
from .reference import COHORTS, PARAM_SPECS, PROFILES
from .schemas import (
    ConfigResponse,
    Profile,
    ScoreRequest,
    ScoreResponse,
    Sex,
)

app = FastAPI(title="Health Scoring API", version="1.0.0")

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse)
def config():
    return {
        "params": [{k: v for k, v in p.items() if k != "weight"} for p in PARAM_SPECS],
        "cohorts": {
            key: {"name": c["name"], "count": c["count"], "means": {pid: s["mean"] for pid, s in c["stats"].items()}}
            for key, c in COHORTS.items()
        },
        "profiles": list(PROFILES),
    }


@app.get("/api/profiles/{name}", response_model=Profile)
def profile(name: str, sex: Sex = "ALL"):
    if name not in PROFILES:
        raise HTTPException(404, f"Unknown profile: {name}")
    return PROFILES[name](sex)


@app.post("/api/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    return scoring.evaluate(
        req.values.model_dump(),
        cohort=req.cohort,
        sex=req.sex,
    )


FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend"))
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
