from typing import List, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .retriever import retrieve_cost_items

app = FastAPI(title="Costbook Retrieval API", version="1.0.0")

# Allow all origins by default; adjust in production as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search", response_model=List[Dict])
async def search_cost_items(query: str = Query(..., min_length=1, description="Search phrase")):
    """Return the top-5 costbook items that semantically match the query."""
    try:
        results = retrieve_cost_items(query)
        return results
    except Exception as exc:
        # Convert unexpected errors into 500 responses
        raise HTTPException(status_code=500, detail=str(exc)) 