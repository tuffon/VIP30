# Bid-comp filename propagation

## Upload (apps/vip-parse/src/routes/s3.py)
- `/render/upload-url` accepts the browser's `filename` and emits an S3 key `uploads/{filename}` plus a presigned PUT URL.
- Whatever basename the frontend submits becomes part of the key. If the frontend generates a tmp-style name, the worker can only recover that tmp name later.

## Frontend upload form (apps/vipclaims-saas/app/bid-comp/page.tsx)
- The Next.js form calls `fetch(${base}/render/upload-url?filename=${encodeURIComponent(file.name)})`, so the browser-provided `File.name` flows unchanged into the presigned key request.
- After uploading, the UI POSTs `/render/bid-comp/keys` with the returned `key` values plus `carrier_filename`/`contractor_filename` fields populated from the same `File.name`.
- Any tmp or sanitized name therefore originates either from the user's filesystem (e.g., downloads named `tmp1234.pdf`) or from an earlier pipeline that rewrote the filename before it touched the UI.

## Enqueue (apps/vip-parse/src/routes/bid_comp.py)
- `/render/bid-comp/keys` requires `carrier_key` and `contractor_key` and simply forwards any optional `carrier_filename` / `contractor_filename` strings into the job payload.
- There is no validation that the optional filenames are present or non-empty, so the worker must fall back to deriving names from S3 keys when these fields are missing.

## Worker (apps/vip-parse/src/tasks.py)
- `run_bid_comp_keys` downloads each key into a temp PDF, then resolves `carrier_original = carrier_filename or Path(carrier_key).name` (and the contractor analogue).
- The resolved name is injected into `carrier_payload.setdefault("original_filename", ...)` and `case_metadata.setdefault("original_filename", ...)` (same for contractor) so downstream consumers can read `original_filename` even if the parser did not emit one.
- The same resolved names become `source_filename` on each `bid_context["estimates"...]` entry plus the top-level `carrier_source_filename` / `contractor_source_filename` fields. If the S3 key basename is `tmp-123.pdf`, that placeholder propagates everywhere.

## Rendering (apps/vip-parse/src/bid_comp/core.py)
- `BidComp._resolve_entry` prefers `source_filename`, then falls back to any `original_filename`/`filename` fields on either the estimate wrapper or payload.
- `_build_estimate` ultimately calls `ensure_estimate_identity` with whichever filename survived, so the workbook, narrative, and recap rows inherit the worker-provided name.

## Net effect
- If the frontend omits `carrier_filename`/`contractor_filename`, the worker depends on `Path(key).name` for both the payload metadata and the rendered sheets.
- Any tmp or opaque basename inserted earlier in the pipeline therefore fans out to every downstream artifact unless the upload request preserves the human-readable `File.name`.

## Observed artifacts
- The generated CSV `results_bc1b58fa-a605-4f82-988e-68408a035399_bid-comp.xlsx - Narrative Summary.csv` shows the comparison estimate labeled `tmp3lom_t_a.pdf`, proving that a tmp-style basename propagated all the way into the client-facing workbook when the worker could not recover a better filename.

## Remediation plan
- **Require human-readable filenames at enqueue time.** `apps/vip-parse/src/routes/bid_comp.py` should validate `carrier_filename` and `contractor_filename` (non-empty strings) and reject requests that omit them, because the Next.js UI already provides these fields. This prevents silent fallbacks for the primary product surface.
- **Log and tag fallback usage.** Instrument `run_bid_comp_keys` to emit a structured warning whenever it falls back to `Path(key).name`, including the offending key. This gives SRE/Support enough telemetry to spot other ingestion sources (e.g., API clients) that still send tmp basenames.
- **Normalize worker payloads.** When the parser produces a meaningful `estimate_name`, use that to overwrite `source_filename` if the resolved name still matches the tmp pattern (e.g., `tmp*.pdf`). This keeps downstream artifacts human-readable even when the upload hop misbehaves.
- **Guard with tests + checks.** Extend the new `test_filename_regression.py` to (a) assert the worker emits a warning metric when it must fall back and (b) ensure upcoming enforcement rejects missing filenames. Add a lightweight smoke test (or CI job) that opens the exported CSV and asserts the comparison labels do not match the `tmp*.pdf` regex, catching regressions before release.
