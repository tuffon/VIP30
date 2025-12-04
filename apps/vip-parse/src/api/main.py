from typing import List, Dict
import logging
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .retriever import retrieve_cost_items
from src.routes.bid_comp import router as bid_comp_router
from src.routes.s3 import router as r2_router
from src.routes.marketing import router as marketing_router

_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("vip-parse.api")

# Quiet Uvicorn access logs (health checks generate lots of noise)
try:
    logging.getLogger("uvicorn.access").disabled = True
except Exception:
    pass

app = FastAPI(title="Costbook Retrieval API", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("FastAPI application starting up (LOG_LEVEL=%s)", _log_level)
    logger.info("Startup ready")

# CORS configuration
# Default: wildcard origins allowed, no credentials (so browsers accept '*').
_cors_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
_cors_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() in {"1", "true", "yes"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bid_comp_router)
app.include_router(r2_router)
app.include_router(marketing_router)

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Costbook API is running"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


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