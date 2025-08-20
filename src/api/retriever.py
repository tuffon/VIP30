from typing import List, Optional, Any
import os

from dotenv import load_dotenv
import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

load_dotenv()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "https://7a89629f-324d-4409-bc4f-da378337c10b.us-west-1-0.aws.cloud.qdrant.io:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not OPENAI_API_KEY or not QDRANT_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY and QDRANT_API_KEY must be provided as environment variables.")

openai.api_key = OPENAI_API_KEY

# Initialize Qdrant client (reuse across calls)
_qdrant_client: Optional[QdrantClient] = None


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
    return _qdrant_client


def _embed_query(query: str) -> List[float]:
    """Embed the query string using OpenAI's text-embedding-3-small model."""
    response = openai.embeddings.create(model="text-embedding-3-small", input=query)
    return response.data[0].embedding


COLLECTION_NAME = "costbook_data"
VECTOR_NAME = None  # use default unnamed vector store


def retrieve_cost_items(query: str) -> List[dict]:
    """Return top-5 costbook items matching the query.

    Args:
        query: Natural-language search phrase.

    Returns:
        A list of payload dictionaries sorted by similarity (best first).
    """
    if not query:
        return []

    qdrant = _get_qdrant_client()
    query_vector = _embed_query(query)

    filter_ = rest.Filter(
        must=[
            rest.FieldCondition(
                key="source_type",
                match=rest.MatchValue(value="bni_csi"),
            )
        ]
    )

    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=filter_,
        with_payload=True,
        limit=5,
    )

    # Extract only payload dictionaries
    return [point.payload or {} for point in results] 