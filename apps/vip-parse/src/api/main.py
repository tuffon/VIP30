from typing import List, Dict, Optional

from fastapi import FastAPI, Form, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .retriever import retrieve_cost_items
from .render import BidCompRenderResponse, process_bid_comp_render

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


@app.post(
    "/render/bid-comp",
    response_model=BidCompRenderResponse,
    summary="Parse estimates and request bid comparison analysis",
)
async def render_bid_comparison(
    carrier_estimate: UploadFile = File(..., description="Carrier or benchmark estimate PDF"),
    contractor_estimate: UploadFile = File(..., description="Contractor or internal bid PDF"),
    prompt_template: Optional[str] = Form(
        default=None,
        description="Optional custom prompt template to override the default analysis prompt",
    ),
    left_label: Optional[str] = Form(
        default=None,
        description="Display label to use for the carrier (Estimate A) side in generated outputs",
    ),
    right_label: Optional[str] = Form(
        default=None,
        description="Display label to use for the contractor (Estimate B) side in generated outputs",
    ),
    row_label_header: Optional[str] = Form(
        default=None,
        description="Header to use for the first column in the CSV output (defaults to 'Category')",
    ),
    model: str = Form(default="gpt-4o-mini", description="OpenAI model identifier"),
    temperature: float = Form(default=0.2, description="OpenAI sampling temperature"),
    max_output_tokens: Optional[int] = Form(
        default=None,
        description="Optional cap on OpenAI response tokens",
    ),
    debug_parser: bool = Form(
        default=False,
        description="Enable verbose parser validations (writes additional metadata)",
    ),
):
    """Render a bid comparison analysis for two uploaded estimates."""

    return await process_bid_comp_render(
        carrier_estimate=carrier_estimate,
        contractor_estimate=contractor_estimate,
        prompt_template=prompt_template,
        left_label_override=left_label,
        right_label_override=right_label,
        row_label_header=row_label_header,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        debug_parser=debug_parser,
    )


@app.get("/render/debug/ping")
async def render_ping():
    """Simple health probe for render integration tests."""
    print("[bid-comp] Received ping")
    return {"status": "ok", "message": "render/bid-comp backend reachable"}


@app.post("/render/debug/echo")
async def render_echo(payload: dict):
    """Echo endpoint to validate JSON POST requests end-to-end."""
    print("[bid-comp] Received echo payload", payload)
    return {"status": "ok", "received": payload}