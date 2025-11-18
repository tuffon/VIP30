# VIP30 – Costbook Embedding Pipeline

This repository contains a small utility for converting a structured **BNI/CSI costbook** JSON file into high–dimensional vectors with OpenAI's embedding model and loading them into a [Qdrant](https://qdrant.tech/) vector database.

The goal is to make construction-cost knowledge query-able with semantic search or RAG pipelines.

---

## Contents

```
├── data/                       # source data (not committed)
│   └── unit_costs1_structured.json
├── embeddings/
│   └── embed_and_upload_bni_costs.py
├── requirements.txt            # Python dependencies
├── .gitignore                  # ignores secrets, venvs, cache …
├── env.example                 # template for environment variables
└── README.md                   # this file
```

---

## Quick start (parser local debug)

1. **Clone** the repo and create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

2. **Install parser dependencies** (for local full-parse debug):

```bash
cd apps/vip-parse
pip install pdfplumber==0.10.0 pypdfium2==4.30.0
```

3. **Configure secrets**:

* Copy `env.example` to `.env` and fill in the values:

```
OPENAI_API_KEY=sk-...
QDRANT_API_KEY=xxxx
```

* The Qdrant Cloud **URL is hard-coded** in the script. If you host your own Qdrant, change the constant `QDRANT_URL` in `embeddings/embed_and_upload_bni_costs.py`.

4. **Place or update the input data** in `data/unit_costs1_structured.json`.

5. **Run the Xactimate parser helper on a PDF**:

```bash
cd apps/vip-parse
python src/worker_parse_helper.py "path/to/estimate.pdf" > out.json
```

This prints a JSON object with:

- `sections`: full parsed sections + line items
- `recap_by_category`: recap view derived from `recaps_and_summaries`

Use this to reproduce and inspect parse behaviour locally without R2/S3 or worker-only dependencies.

---

## How it works

1. The script loads environment variables with `python-dotenv`.
2. It iterates over the costbook records, builds a descriptive text prompt, and requests an embedding from the model `text-embedding-3-small`.
3. Each record is stored in Qdrant with:
   * a 1 536-dimensional vector,
   * the original metadata (code, unit, cost, etc.).
4. To stay within Qdrant Cloud's 32 MB HTTP limit the points are **upserted in batches**.
5. A 60 s HTTP timeout is set to avoid write time-outs on slower networks.

---

## Environment & secrets

• Secrets are **never** checked into git. They live only in your local `.env` which is ignored by `.gitignore`.

• If you rotate keys, just update the `.env` file – no code changes required.

---

## Extending / customising

* **Different embedding model** – edit the `model="..."` string.
* **Other JSON file** – change the file path or parameterise it.
* **Other vector store** – swap the Qdrant client for your preferred database.

---

## License

MIT (see `LICENSE` if present).
