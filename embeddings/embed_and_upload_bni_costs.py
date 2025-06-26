import json
import uuid
import os
from dotenv import load_dotenv
import openai
from tqdm import tqdm
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from qdrant_client import QdrantClient

# === Configuration ===
# Load environment variables from a .env file (if present) and the OS environment
load_dotenv()

# Mandatory environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = "https://7a89629f-324d-4409-bc4f-da378337c10b.us-west-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not all([OPENAI_API_KEY, QDRANT_API_KEY]):
    raise EnvironmentError(
        "OPENAI_API_KEY and QDRANT_API_KEY must be set as environment variables."
    )

COLLECTION_NAME = "costbook_data"
VECTOR_SIZE = 1536  # for text-embedding-3-small

# === Qdrant Client ===
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

# === Create collection if not exists ===
collections = qdrant_client.get_collections().collections
if COLLECTION_NAME not in [c.name for c in collections]:
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
    print(f"✅ Created collection '{COLLECTION_NAME}'")

# === Load JSON Data from sibling 'data' directory ===
with open("data/unit_costs1_structured.json", "r") as f:
    data = json.load(f)

# === Embedding Function ===
def embed(text):
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

# === Generate and Upload Points ===
BATCH_SIZE = 500  # Maximum points per upsert call to stay under Qdrant's 32 MB payload limit
points_batch = []
uploaded_total = 0

for item in tqdm(data):
    input_text = (
        f"bni_csi | Code: {item.get('code')} | Division: {item.get('main_division')} | "
        f"Subdivision: {item.get('subdivision')} | Classification: {item.get('major_classification')} | "
        f"Description: {item['description']}"
    )

    vector = embed(input_text)

    payload = {
        "code": item.get("code"),
        "unit": item.get("unit"),
        "unit_cost": item.get("unit_cost"),
        "main_division": item.get("main_division"),
        "subdivision": item.get("subdivision"),
        "major_classification": item.get("major_classification"),
        "description": item["description"],
        "source_type": "bni_csi",
        "version": "2025",
        "embedding_model": "text-embedding-3-small"
    }

    points_batch.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))

    # Upload when the batch size limit is reached
    if len(points_batch) >= BATCH_SIZE:
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points_batch)
        uploaded_total += len(points_batch)
        points_batch = []

# === Upload any remaining points ===
if points_batch:
    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points_batch)
    uploaded_total += len(points_batch)

print(f"✅ Uploaded {uploaded_total} items to Qdrant.")
