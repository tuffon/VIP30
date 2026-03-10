# Stack Research: v2.6 Pipeline Rewrite

**Research date:** 2026-03-09
**Milestone:** v2.6 Pipeline Rewrite
**Question:** What's the right technical approach for a per-cost-driver LLM architecture on top of the existing Python/OpenAI stack?

---

## Current Stack (Confirmed from Codebase)

- **LLM calls:** OpenAI via `LLMAdapterBase` — `generate()` (raw text) and `generate_structured()` (Pydantic structured outputs)
- **Pipeline:** Synchronous Python in `packages/shared-python/vip_shared/pipeline/`
- **Execution:** RQ worker, long-running jobs already queued async
- **Caching:** Redis with content-hash keys (1hr analysis, 30min writer, compliance uncached)
- **Models:** Pydantic v2 throughout (`AnalysisResult`, `DraftNarrative`, `DriverNarrative`, etc.)
- **Parser output:** `recaps_and_summaries.recap_by_category` available on all doc types; `trade_summary` on StateFarm final-draft only

---

## Plain Python vs LangChain

**Recommendation: Plain Python** (no LangChain)

Rationale:
- Existing `LLMAdapterBase` already abstracts the OpenAI call; adding LangChain adds a framework layer with no benefit here
- Per-driver calls are simple sequential API calls with different prompts — no chains, no agents, no memory needed
- LangChain's strengths (multi-step chains, memory, tools) add complexity for a pipeline that's structurally parallel-and-aggregate
- User preference: plain Python if simpler — it is simpler here

LangChain would only make sense if: using RAG, complex tool-calling chains, or memory across many turns. None apply here.

---

## Async vs Synchronous

**Recommendation: Synchronous with potential future async**

Current situation:
- Entire pipeline is synchronous — each pass calls LLM and waits
- RQ worker handles job-level async (the job itself is one unit of work)
- Per-driver LLM calls could theoretically be parallelized with `asyncio.gather()` or `ThreadPoolExecutor`

For v2.6:
- Start synchronous — simpler, matches existing patterns, easier to debug
- A 5-driver job = 5 sequential LLM calls + 1 summary call = ~6 calls total
- At ~1-2s per call, total = 6-12s. Acceptable for a worker job.
- Parallelize only if profiling shows it's a bottleneck (v2.7+)

**Do not refactor to async for v2.6.** The existing RQ worker infrastructure handles job-level concurrency; per-request parallelization is premature optimization.

---

## OpenAI Structured Outputs

**Recommendation: Extend existing `generate_structured()` pattern**

Current usage:
- Analysis pass uses `generate_structured("analysis_pass_v1", context, response_model=LLMAnalysisResult)` — Pydantic model enforces schema
- Writer/compliance passes use `generate()` with JSON parsing fallback (and fragile `_repair_json` hacks)

For v2.6:
- Per-driver pass: define a `DriverAnalysisResult` Pydantic model; use `generate_structured()` — eliminates JSON parse failures
- Final summary pass: define a `SummaryResult` Pydantic model; use `generate_structured()`
- Quality gate: keep existing deterministic `QualityEvaluator` checkers (GATE-01 through GATE-05)

**Advantages of structured outputs for per-driver calls:**
- No JSON repair hacks (already present in writer.py `_repair_json` — a symptom of not using structured outputs)
- Pydantic validation catches schema violations at call time
- Consistent with analysis pass pattern already established

---

## Prompt Templates

Current system: JSON files referenced by template ID (e.g., `"analysis_pass_v1"`, `"writer_pass_v2"`)

For v2.6, new templates needed:
- `"driver_analysis_v1"` — per-driver system + user prompt (trade context + line items → narrative)
- `"final_summary_v1"` — aggregate summary prompt (all driver narratives → executive overview)
- `"quality_rewrite_v1"` — single-pass compliance rewrite (replaces `compliance_rewrite_v1/v2`)

Existing templates (`analysis_pass_v1`, `writer_pass_v1/v2`, `compliance_rewrite_v1/v2`) are **deprecated** — no longer called by new pipeline. Keep temporarily for rollback safety.

---

## Caching Strategy

Current: Content-hash keys on `EstimatePair` data

For v2.6:
- Per-driver cache key = hash of (driver_category + driver_line_items + trade_context)
- Final summary cache key = hash of (all driver analysis outputs)
- TTL: 1hr for all passes (match existing policy)
- **Compliance pass eliminated** — no separate cache concern

Benefit: re-run with same PDFs skips individual driver LLM calls if data unchanged. Critical for debugging and retries.

---

## No New Dependencies Required

All needed capabilities already exist:
- `openai` → already in requirements
- `pydantic` → already in use
- `redis` → already in use for caching
- `vip_parser` → parser package already produces structured JSON with `recap_by_category`

**Do not add:** LangChain, LlamaIndex, instructor, outlines, or other LLM orchestration frameworks.

---

## Confidence Assessment

| Decision | Confidence | Rationale |
|----------|------------|-----------|
| Plain Python over LangChain | High | No framework features needed; existing adapter sufficient |
| Synchronous calls | High | Simpler, matches existing patterns, perf acceptable |
| `generate_structured()` for new passes | High | Analysis pass already uses it successfully |
| New template IDs for new passes | High | Existing template system is the right abstraction |
| No new dependencies | High | All needed primitives already present |
