from typing import List, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .retriever import retrieve_cost_items

app = FastAPI(title="Costbook Retrieval API", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("FastAPI application starting up...")
    try:
        # Test the retriever initialization
        from .retriever import _get_qdrant_client
        _get_qdrant_client()
        print("Application startup completed successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize retriever during startup: {e}")
        print("Application will start but search functionality may not work")

# Allow all origins by default; adjust in production as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Costbook API is running"}


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