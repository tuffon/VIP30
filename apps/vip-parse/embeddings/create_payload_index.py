from dotenv import load_dotenv
import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import PayloadSchemaType

load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://7a89629f-324d-4409-bc4f-da378337c10b.us-west-1-0.aws.cloud.qdrant.io:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "costbook_data"

if not QDRANT_API_KEY:
    raise EnvironmentError("QDRANT_API_KEY environment variable must be set.")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

try:
    created = client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="source_type",
        field_schema=PayloadSchemaType.KEYWORD,
        wait=True,
    )
    if created:
        print("✅ Payload index on 'source_type' created.")
    else:
        print("ℹ️  Payload index on 'source_type' already exists.")
except Exception as exc:
    print(f"❌ Failed to create index: {exc}") 