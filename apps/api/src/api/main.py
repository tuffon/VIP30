from typing import List, Dict
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .logging_config import configure_logging, get_logger
from .middleware import RequestIDMiddleware
from .retriever import retrieve_cost_items

_log_level = configure_logging()
logger = get_logger("vip-parse.api")

from vip_shared.db import async_engine
from src.routes.auth import auth_router
from src.routes.bid_comp import router as bid_comp_router
from src.routes.credits import credits_router
from src.routes.jobs import jobs_router
from src.routes.s3 import router as r2_router
from src.routes.marketing import router as marketing_router

app = FastAPI(title="Costbook Retrieval API", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("api_starting", extra={"log_level": _log_level})
    logger.info("startup_ready")

# CORS configuration for cookie-based auth.
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,https://vip30-frontend.onrender.com"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(bid_comp_router)
app.include_router(r2_router)
app.include_router(marketing_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(credits_router)

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Costbook API is running"}


@app.get("/health")
async def health():
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(exc)},
        )


@app.get("/healthz")
async def healthz():
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(exc)},
        )


@app.get("/debug")
async def debug_info():
    """Debug endpoint to check environment and configuration."""
    import os
    return {
        "status": "debug",
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "qdrant_key_set": bool(os.getenv("QDRANT_API_KEY")),
        "qdrant_url": os.getenv("QDRANT_URL", "not set"),
        "working_directory": os.getcwd(),
    }


@app.get("/search", response_model=List[Dict])
async def search_cost_items(query: str = Query(..., min_length=1, description="Search phrase")):
    """Return the top-5 costbook items that semantically match the query."""
    try:
        results = retrieve_cost_items(query)
        return results
    except Exception as exc:
        # Convert unexpected errors into 500 responses
        raise HTTPException(status_code=500, detail=str(exc)) 

# removed legacy debug endpoints
