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
cd apps/worker
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
cd apps/worker
python src/worker_parse_helper.py "path/to/estimate.pdf" > out.json
```

This prints a JSON object with:

- `sections`: full parsed sections + line items
- `recap_by_category`: recap view derived from `recaps_and_summaries`

Use this to reproduce and inspect parse behaviour locally without R2/S3 or worker-only dependencies.

---

## Visible text filtering

Xactimate PDFs sometimes include hidden overlay text (white-on-white, invisible render mode) that confuses the parser. The module `parse/xactimate/visible_text.py` filters those characters before we reconstruct lines. You can tune the heuristics via environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `VISIBLE_TEXT_WHITE_THRESHOLD` | RGB/grayscale value ≥ this is treated as “white”. Accepts 0–1 or 0–255. | `0.97` |
| `VISIBLE_TEXT_MIN_FONT_SIZE` | Drop chars smaller than this font size. | `2.0` |
| `VISIBLE_TEXT_DROP_WHITE` | Disable to keep white text even when background is white. | `true` |
| `VISIBLE_TEXT_DROP_INVISIBLE_MODE` | Disable to keep chars rendered with `text_rendering_mode=3`. | `true` |
| `VISIBLE_TEXT_DROP_OUT_OF_BOUNDS` | Disable to keep glyphs positioned outside the page box. | `true` |
| `VISIBLE_TEXT_BOUNDARY_MARGIN` | Extra margin (pts) before a glyph is considered out-of-bounds. | `1.0` |
| `VISIBLE_TEXT_DROP_SMALL_OVERLAY` | Disable to keep tiny overlay runs (≤ overlay max font). | `true` |
| `VISIBLE_TEXT_OVERLAY_MAX_FONT` | Maximum font size (pt) treated as “overlay” for duplicate/OOB tests. | `7.5` |
| `VISIBLE_TEXT_OVERLAY_MIN_CHARS` | Minimum glyphs per baseline before overlay heuristics trigger. | `6` |
| `VISIBLE_TEXT_OVERLAY_DUP_RATIO` | Duplicate ratio threshold (0–1) required to drop a small-font baseline. | `0.35` |
| `VISIBLE_TEXT_OVERLAY_DUP_MAX_SPAN` | Max x-span (pt) for duplicate-based drops; wider baselines are kept (0 = disable guard). | `0.0` |
| `VISIBLE_TEXT_OVERLAY_SPAN_MIN_FONT` | Ignore glyphs smaller than this when computing duplicate span. | `3.0` |
| `VISIBLE_TEXT_OVERLAY_TOP_TOL` | Baseline grouping tolerance in points (higher = looser). | `0.5` |
| `VISIBLE_TEXT_OVERLAY_X_TOL` | Horizontal tolerance in points when counting duplicate glyphs. | `0.25` |
| `VISIBLE_TEXT_OVERLAY_OOB_RATIO` | Fraction of glyphs outside the page bounds that triggers a drop. | `0.25` |
| `VISIBLE_TEXT_DROP_MEASUREMENT_OVERLAY` | Disable to keep isolated measurement ticks (feet/inches). | `true` |
| `VISIBLE_TEXT_MEASUREMENT_MAX_FONT` | Max font size for measurement ticks to be dropped. | `7.5` |
| `VISIBLE_TEXT_MEASUREMENT_MAX_SPAN` | Max width (pt) for measurement ticks; wider groups are kept. | `30.0` |
| `VISIBLE_TEXT_MEASUREMENT_MIN_CHARS` | Minimum glyphs before measurement logic triggers. | `2` |
| `VISIBLE_TEXT_MEASUREMENT_ALLOWED_CHARS` | Whitelist of characters treated as measurement ticks. | `0123456789'" .-/` |
| `VISIBLE_TEXT_DEBUG_PAGES` | Comma-separated 1-based page numbers or `all` to log debug summaries. | unset |
| `VISIBLE_TEXT_DEBUG_SAMPLE_LINES` | How many raw vs filtered lines to log when debugging. | `3` |
| `VISIBLE_TEXT_DEBUG_LOG_COLORS` | When true, log per-page color bucket counts. | `false` |

These knobs let you tighten or relax the filters without touching code when new PDF samples surface.

Small-font overlay noise (e.g., duplicated 6 pt glyphs layered over totals) is handled by grouping characters that share a baseline and font size. If most glyphs in that group either duplicate their neighbors or spill off the page, the entire run is discarded before any downstream parsing happens. Tweak the overlay-specific settings above if future samples require looser or stricter behavior.

Dimension ticks (e.g., `6' 2"` labels that Xactimate prints above a real row) are treated as measurement overlays: when the glyphs are tiny, span < 30 pt, and consist only of digits/quotes/punctuation, they are removed prior to line reconstruction. This keeps genuine lines like `Utility Room Height: 8'` intact while stripping the duplicate measurement markers that otherwise splice into totals.

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
