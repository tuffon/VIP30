# Architecture Research: v2.0 Analytical Intelligence

**Domain:** Insurance estimate comparison analytics
**Researched:** 2026-02-17
**Confidence:** HIGH (based on direct codebase analysis -- all recommendations derived from existing code structure)

## Executive Summary

The v2.0 features (rules engine, methodology analysis, output modes, enhanced XLSX) integrate as layers around the existing 3-pass LLM pipeline rather than replacing it. The key architectural insight: the current `BidComp.run()` method already follows a sequential pipeline pattern (build_pair -> category_table -> top_deltas -> narrative -> export_xlsx). The v2.0 additions slot into this pipeline as pre-analysis enrichment (before the LLM pipeline) and post-analysis output shaping (after the LLM pipeline, before export).

The existing `PipelineState` Pydantic model is the natural extension point. New components produce typed artifacts that attach to the state, and the export layer reads from state rather than from scattered arguments.

**Primary recommendation:** Build v2.0 as three new module directories (`src/rules/`, `src/methodology/`, `src/output_modes/`) that produce typed Pydantic models consumed by the existing pipeline and export layer. Do not restructure the existing pipeline orchestrator.

## Current Pipeline Architecture

```
CURRENT (v1.x):
===============

 PDF Upload (S3) --> Worker picks up job
                          |
                    [XactimateParser]
                    Parse both PDFs
                          |
                    [BidComp._build_pair]
                    Build EstimatePair with recaps, totals, snapshots
                          |
                    [BidComp._build_category_table]
                    Aggregate recap data into 24 Verisk categories
                          |
                    [BidComp._top_deltas]
                    Select top N categories by absolute delta
                          |
                    [NarrativePipeline.run]  <--- 3-pass LLM pipeline
                    |  Pass 1: Analysis (extract structured deltas)
                    |  Pass 2: Writer (adjuster-tone narratives)
                    |  Pass 3: Compliance (conditional quality rewrite)
                          |
                    [export_xlsx]
                    3 sheets: Narrative Summary, Verisk Categories, Original Recap
                          |
                    Upload XLSX to S3 --> Presigned URL to user
```

## Enhanced Pipeline Architecture (v2.0)

```
PROPOSED (v2.0):
================

 PDF Upload (S3) --> Worker picks up job
                          |
                    [XactimateParser]
                    Parse both PDFs (full parse, not recap-only)
                          |
                    [BidComp._build_pair]
                    Build EstimatePair (unchanged)
                          |
                    [BidComp._build_category_table]
                    Aggregate Verisk categories (unchanged)
                          |
              +-----------+-----------+
              |                       |
    [MethodologyAnalyzer]    [BidComp._top_deltas]
    NEW: Pre-LLM analysis    (unchanged)
    - O&P detection                |
    - Depreciation diff            |
    - Unit pricing source          |
    - Locality factors             |
    - Scope completeness           |
              |                    |
              +--------+----------+
                       |
                 [RulesEngine]
                 NEW: Pre-LLM signal extraction
                 Input: EstimatePair + category_table + MethodologyResult
                 Output: SignalBundle (emphasis flags, alert tags, patterns)
                       |
                 [NarrativePipeline.run]  <--- ENHANCED 3-pass LLM pipeline
                 Pass 1: Analysis (now receives MethodologyResult + SignalBundle)
                 Pass 2: Writer (evidence-based, neutral tone, signal-aware)
                 Pass 3: Compliance (enhanced quality gates)
                       |
                 [PipelineState] now contains:
                 - analysis: AnalysisResult (existing)
                 - methodology: MethodologyResult (NEW)
                 - signals: SignalBundle (NEW)
                 - draft/final: FinalNarrative (existing, enhanced)
                       |
                 [OutputModeFilter]
                 NEW: Content filtering by mode
                 Input: PipelineState (full analysis)
                 Output: ModeFilteredOutput (subset for requested mode)
                       |
                 [EnhancedXLSXExporter]
                 ENHANCED: Multi-sheet, conditional formatting
                 Input: ModeFilteredOutput
                 Output: XLSX bytes
                       |
                 Upload XLSX to S3
```

## New Components

| Component | Module Path | Responsibility | Integration Point | Input | Output |
|-----------|-------------|----------------|-------------------|-------|--------|
| MethodologyAnalyzer | `src/methodology/analyzer.py` | Detect O&P structure, depreciation, unit pricing, locality, scope completeness | Between `_build_pair` and `NarrativePipeline.run` | `EstimatePair` | `MethodologyResult` |
| RulesEngine | `src/rules/engine.py` | Flag meaningful patterns, generate alert tags, detect emphasis signals | After MethodologyAnalyzer, before pipeline | `EstimatePair`, `category_rows`, `MethodologyResult` | `SignalBundle` |
| OutputModeFilter | `src/output_modes/filter.py` | Select/reshape content for 4 output modes | After pipeline, before export | `PipelineState`, `OutputMode` enum | `ModeFilteredOutput` |
| EnhancedXLSXExporter | `src/bid_comp/export_xlsx_v2.py` | Multi-sheet XLSX with conditional formatting, exec summary | Replaces `export_xlsx` | `ModeFilteredOutput` | `bytes` |

## Component Details

### 1. MethodologyAnalyzer (`src/methodology/`)

**What it does:** Pure Python analysis (no LLM) that examines parsed estimate data to detect structural methodology differences between the two estimates.

**Why pre-LLM:** Methodology detection is deterministic pattern matching on parsed data. Running it before the LLM pipeline means the analysis pass gets richer context without additional token cost. The LLM can reference concrete methodology findings rather than discovering them from raw data.

**Key detection targets:**
- O&P inclusion: Does each estimate include overhead & profit? What percentage? Are they applied per-line or as lump sum?
- Depreciation: Is depreciation applied? RCV vs ACV handling differences?
- Unit pricing source: Xactimate version/price list date differences
- Locality factors: Geographic pricing modifier differences
- Scope completeness: Sections present in one estimate but missing in the other

**Data model:**
```python
# src/methodology/models.py
class MethodologyResult(BaseModel):
    op_comparison: OPComparison          # O&P structure diff
    depreciation_comparison: DepreciationComparison
    pricing_metadata: PricingMetadata    # unit price sources
    scope_completeness: ScopeCompleteness  # present/missing sections
    structural_flags: List[StructuralFlag]  # high-level methodology issues
```

**Integration:** Called in `BidComp.run()` after `_build_pair()`, result passed to pipeline via `PipelineState`.

**Data sources within parsed payload:**
- `case_metadata.line_item_totals` contains O&P amounts (already extracted by parser)
- `recaps_and_summaries.subtotals` contains O&P, tax, permit fee breakdowns
- `sections[].line_items[].type` distinguishes line items from O&P entries
- `case_metadata` may contain Xactimate version, price list date
- `sections[].section_name` for scope presence/absence comparison

### 2. RulesEngine (`src/rules/`)

**What it does:** Applies configurable threshold rules to produce emphasis signals and alert tags. This is the "intelligence layer" that decides what matters most.

**Why a rules engine (not ad-hoc logic):** Rules are the primary way to ensure consistent, explainable emphasis. Every flagged pattern can be traced to a named rule with a threshold. This is critical for litigation readiness -- the system must be able to explain WHY something was flagged.

**Rule categories:**
```python
# src/rules/models.py
class SignalBundle(BaseModel):
    emphasis_flags: List[EmphasisFlag]  # top 20% variance, threshold breaches
    alert_tags: List[AlertTag]          # O&P gaps, large Other, scope imbalance
    pattern_detections: List[PatternDetection]  # partial vs full restoration
    ranked_impacts: List[RankedImpact]  # sorted by magnitude for impact table
```

**Rule examples:**
| Rule ID | Name | Trigger | Output |
|---------|------|---------|--------|
| EMPH-01 | Top variance drivers | Category delta in top 20% of total variance | EmphasisFlag with magnitude rank |
| EMPH-02 | Large absolute delta | Category delta > $5,000 | EmphasisFlag |
| EMPH-03 | Large percentage delta | Category delta > 50% of smaller estimate | EmphasisFlag |
| ALERT-01 | Missing O&P | One estimate has O&P, other does not | AlertTag(severity=HIGH) |
| ALERT-02 | Large Other bucket | "Other/Unclassified" > 15% of total | AlertTag(severity=MEDIUM) |
| ALERT-03 | Scope imbalance | >3 categories present in one, absent in other | AlertTag(severity=HIGH) |
| ALERT-04 | Depreciation mismatch | One uses ACV, other uses RCV | AlertTag(severity=HIGH) |
| PATTERN-01 | Partial restoration | Categories suggest repair-only vs full replace | PatternDetection |

**Implementation approach:** Rules are Python dataclasses with a `matches(context) -> bool` method and an `emit(context) -> Signal` method. A `RuleSet` iterates registered rules over the analysis context. Rules are registered in code (not config files) for v2.0 -- configuration can be added later.

```python
# src/rules/engine.py
class RulesEngine:
    def __init__(self, rules: List[Rule] | None = None):
        self.rules = rules or default_rules()

    def evaluate(
        self,
        pair: EstimatePair,
        category_rows: List[Dict],
        methodology: MethodologyResult,
    ) -> SignalBundle:
        context = RuleContext(pair=pair, categories=category_rows, methodology=methodology)
        signals = SignalBundle()
        for rule in self.rules:
            if rule.matches(context):
                signal = rule.emit(context)
                signals.add(signal)
        signals.rank_impacts()
        return signals
```

### 3. OutputModeFilter (`src/output_modes/`)

**What it does:** Applies mode-specific content selection and reshaping to the full analysis result. All four modes consume the SAME underlying analysis -- modes are filters, not separate generation paths.

**The four modes:**
| Mode | Content Strategy | What's Included | What's Excluded |
|------|-----------------|-----------------|-----------------|
| Executive | 1-page compressed | Executive snapshot, top 3 drivers, structural flags, total delta | Line item details, full methodology, detailed scope matrix |
| Carrier Negotiation | Ranked delta + methodology | Ranked impact table, methodology analysis, O&P comparison, evidence | Suggested follow-ups (carrier already knows next steps) |
| Litigation | Neutral + evidence | Full scope matrix, neutral-tone narratives, evidence exhibits, methodology | Recommendations, subjective observations |
| Internal Estimator | Deep diagnostic | Everything: full line item deltas, all categories, scope detail, methodology | Nothing excluded -- full depth |

**Data model:**
```python
# src/output_modes/models.py
class OutputMode(str, Enum):
    EXECUTIVE = "executive"
    CARRIER = "carrier"
    LITIGATION = "litigation"
    INTERNAL = "internal"

class ModeFilteredOutput(BaseModel):
    mode: OutputMode
    executive_snapshot: Optional[ExecutiveSnapshot]  # always present
    narrative_sections: Dict[str, Any]               # mode-filtered
    methodology_block: Optional[MethodologyResult]   # excluded in executive
    signal_bundle: Optional[SignalBundle]             # always present
    impact_table: List[RankedImpact]                 # always present, depth varies
    scope_matrix: Optional[ScopeAlignmentMatrix]     # excluded in executive
    include_line_items: bool                          # only true for internal
```

**Implementation:** The filter is a pure function, not a class hierarchy. Each mode defines which fields to include/exclude and any reshaping logic.

```python
# src/output_modes/filter.py
def filter_output(state: PipelineState, mode: OutputMode) -> ModeFilteredOutput:
    """Pure function: full state -> mode-specific output."""
    # Every mode gets executive snapshot and impact table
    snapshot = build_executive_snapshot(state)
    impacts = state.signals.ranked_impacts

    if mode == OutputMode.EXECUTIVE:
        return ModeFilteredOutput(
            mode=mode,
            executive_snapshot=snapshot,
            narrative_sections=_compress_narrative(state.final),
            impact_table=impacts[:3],  # top 3 only
            ...
        )
    # ... other modes
```

### 4. Enhanced XLSX Exporter (`src/bid_comp/export_xlsx_v2.py`)

**What it does:** Generates multi-sheet XLSX with conditional formatting, executive summary sheet, and mode-appropriate content.

**Sheet structure by mode:**

| Sheet | Executive | Carrier | Litigation | Internal |
|-------|-----------|---------|------------|----------|
| Executive Summary | YES (primary) | YES | YES | YES |
| Ranked Impact Table | Top 3 | Full | Full | Full |
| Methodology Analysis | -- | YES | YES | YES |
| Scope Alignment Matrix | -- | -- | YES | YES |
| Verisk Category Matrix | -- | YES | YES | YES |
| Line Item Details | -- | -- | -- | YES |
| Original Recap | -- | -- | YES | YES |
| Alert Tags | Summary only | Full | Full | Full |

**Why export_xlsx_v2.py (new file, not modify existing):**
- The current `export_xlsx.py` is 584 lines and tightly coupled to the current `NarrativeResult` structure
- v2.0 introduces fundamentally new inputs (`ModeFilteredOutput` instead of `NarrativeResult`)
- The old exporter remains as fallback if v2 pipeline components fail
- Once v2 is stable, v1 exporter can be removed

**Conditional formatting rules:**
- Deltas > 20%: red fill
- Deltas > 50%: bold red fill
- Alert tags: icon + colored sidebar
- O&P missing: yellow highlight on affected rows
- Executive snapshot: bordered summary block with key metrics

## Data Flow Diagram

```
EstimatePair
    |
    |--- MethodologyAnalyzer.analyze(pair) --> MethodologyResult
    |         |
    |--- _build_category_table(pair) --> category_rows
    |         |
    |--- _top_deltas(category_rows) --> top_deltas
    |         |
    +----+----+
         |
    RulesEngine.evaluate(pair, category_rows, methodology) --> SignalBundle
         |
    PipelineState(pair, top_deltas, methodology, signals)
         |
    NarrativePipeline.run(state)
    |  Pass 1: AnalysisInput now includes methodology + signals
    |  Pass 2: WriterInput now includes emphasis flags + alert context
    |  Pass 3: Compliance with enhanced quality gates
         |
    PipelineState (fully populated)
         |
    OutputModeFilter.filter(state, mode) --> ModeFilteredOutput
         |
    EnhancedXLSXExporter.export(filtered) --> bytes
```

## PipelineState Extension

The existing `PipelineState` (Pydantic model in `src/pipeline/state.py`) is the extension point. Add new fields with defaults so existing code continues working:

```python
# Extended PipelineState (backwards compatible)
class PipelineState(BaseModel):
    # --- Existing fields (unchanged) ---
    pair: Any = None
    top_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    analysis: Optional[AnalysisResult] = None
    draft: Optional[DraftNarrative] = None
    final: Optional[Union[DraftNarrative, FinalNarrative]] = None
    quality_report: Optional[QualityReport] = None
    passes_executed: List[str] = Field(default_factory=list)
    pass_timings_ms: Dict[str, int] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    # --- v2.0 additions (all Optional with None default) ---
    methodology: Optional[MethodologyResult] = None
    signals: Optional[SignalBundle] = None
    category_rows: Optional[List[Dict[str, Any]]] = None
```

## Integration with Existing BidComp.run()

The current `BidComp.run()` method (line 282-322 of `core.py`) orchestrates the pipeline. The v2.0 changes slot in naturally:

```python
# BidComp.run() with v2.0 additions (pseudocode showing insertion points)
def run(self, bid_context: dict, job_id: str, output_mode: OutputMode = OutputMode.INTERNAL) -> bytes:
    pair = self._build_pair(bid_context)
    category_rows = self._build_category_table(pair)
    top_deltas = self._top_deltas(category_rows)

    # --- v2.0 NEW: Pre-LLM enrichment ---
    methodology = self._methodology_analyzer.analyze(pair) if self._methodology_analyzer else None
    signals = self._rules_engine.evaluate(pair, category_rows, methodology) if self._rules_engine else None

    # --- Existing: LLM pipeline (enhanced inputs) ---
    narrative = self._generate_narrative(pair, top_deltas)  # pipeline now receives methodology + signals via state

    # --- v2.0 NEW: Output mode filtering ---
    filtered = filter_output(state, output_mode) if output_mode else None

    # --- v2.0 ENHANCED: Export ---
    if filtered:
        xlsx_bytes = export_xlsx_v2(filtered=filtered, pair=pair)
    else:
        xlsx_bytes = export_xlsx(pair=pair, narrative=narrative, ...)  # v1 fallback

    return xlsx_bytes
```

**Key design principle:** Every v2.0 addition is guarded by `if component else None`. The existing pipeline continues to work even if v2.0 components are not initialized. This enables incremental build and deploy.

## Suggested Build Order

The dependencies between components dictate build order:

### Phase 1: Methodology Foundation (no LLM changes needed)
**Build:** `src/methodology/` module
**Why first:** MethodologyResult is consumed by RulesEngine and the LLM pipeline. It is pure Python (no LLM calls), fully testable in isolation, and produces the data foundation that everything else builds on.
**Deliverable:** `MethodologyAnalyzer` that reads `EstimatePair` and emits `MethodologyResult`
**Test strategy:** Unit tests with fixture estimate payloads
**Dependencies:** EstimatePair (existing)

### Phase 2: Rules Engine (no LLM changes needed)
**Build:** `src/rules/` module
**Why second:** Consumes MethodologyResult (Phase 1 output) plus existing category data. Still pure Python, still no LLM changes. Produces SignalBundle which is the intelligence layer.
**Deliverable:** `RulesEngine` with initial rule set, `SignalBundle` output
**Test strategy:** Unit tests with known category/methodology inputs, verify flag/tag emission
**Dependencies:** MethodologyResult (Phase 1), EstimatePair (existing), category_rows (existing)

### Phase 3: Enhanced LLM Pipeline Integration
**Build:** Modify `src/pipeline/` to consume MethodologyResult + SignalBundle
**Why third:** Now that pre-LLM components produce typed data, thread that data into the existing pipeline. The analysis pass prompt gets methodology context. The writer pass prompt gets signal emphasis. Quality gates get enhanced checks (neutral tone for litigation mode).
**Deliverable:** Enhanced prompts, updated `PipelineState`, mode-aware quality gates
**Test strategy:** Pipeline integration tests with real LLM calls, compare output quality
**Dependencies:** Phases 1-2 outputs, existing pipeline (modify in place)

### Phase 4: Output Mode System
**Build:** `src/output_modes/` module
**Why fourth:** Requires the full enriched pipeline state from Phase 3 to have meaningful content to filter. The filter itself is pure Python -- it just selects/reshapes data.
**Deliverable:** `OutputModeFilter` with 4 mode implementations
**Test strategy:** Unit tests with mock PipelineState, verify inclusion/exclusion per mode
**Dependencies:** Enhanced PipelineState (Phase 3)

### Phase 5: Enhanced XLSX Export
**Build:** `src/bid_comp/export_xlsx_v2.py`
**Why last:** Requires ModeFilteredOutput (Phase 4) as input. This is the presentation layer -- it reads from the fully enriched, mode-filtered data and produces the final deliverable.
**Deliverable:** Multi-sheet XLSX with conditional formatting, executive summary
**Test strategy:** Generate XLSX from test data, verify sheet structure, formatting, content per mode
**Dependencies:** ModeFilteredOutput (Phase 4), openpyxl (existing)

### Phase 6: API + Frontend Integration
**Build:** API endpoint changes (output_mode parameter), frontend mode selector
**Why last:** The backend pipeline must be complete before exposing mode selection. Frontend changes are minimal -- add a dropdown for output mode before job submission.
**Deliverable:** `output_mode` query param on bid-comp endpoint, frontend selector
**Dependencies:** All backend phases complete

```
Build dependency graph:

Phase 1 (Methodology) --+
                         +--> Phase 3 (Pipeline Integration) --> Phase 4 (Output Modes) --> Phase 5 (XLSX) --> Phase 6 (API/FE)
Phase 2 (Rules Engine) --+
```

Phases 1 and 2 can be built in parallel -- they share no dependencies on each other. Phase 3 requires both. Phases 4-6 are sequential.

## Anti-Patterns to Avoid

### 1. Don't make output modes call the LLM differently
**Anti-pattern:** Running different LLM prompts per output mode (4x cost, 4x latency)
**Correct approach:** Run the full analysis pipeline ONCE. Output modes are post-LLM filters on the same rich result. The constraint from the project context -- "output modes are content filtering, not separate templates" -- is the right architecture.

### 2. Don't put rules logic inside LLM prompts
**Anti-pattern:** Asking the LLM to "flag important differences" or "detect methodology issues"
**Correct approach:** Rules engine runs deterministic Python code BEFORE the LLM. The LLM receives pre-computed signals and writes narratives ABOUT them. This is faster, cheaper, more predictable, and auditable.

### 3. Don't merge methodology analysis into the existing analysis pass
**Anti-pattern:** Adding methodology detection to the LLM analysis pass prompt
**Correct approach:** Methodology analysis is structural/numerical comparison of parsed data. It does not require LLM inference. Running it in Python before the LLM pipeline means: (a) it is deterministic and testable, (b) it adds zero token cost, (c) the LLM can reference concrete findings.

### 4. Don't create a monolithic "v2 pipeline" that replaces everything
**Anti-pattern:** Rewriting `BidComp` and `NarrativePipeline` from scratch
**Correct approach:** Add new modules alongside existing code. Guard v2 features with Optional types and `if component else None`. The existing pipeline continues to work unmodified until v2 components are proven.

### 5. Don't make the XLSX exporter handle mode logic
**Anti-pattern:** `export_xlsx_v2(pair, narrative, mode)` with mode-switching inside the exporter
**Correct approach:** The exporter receives `ModeFilteredOutput` which has already been filtered. The exporter just renders what it receives. Separation of concerns: filter decides WHAT, exporter decides HOW.

### 6. Don't add output_mode to the LLM template context
**Anti-pattern:** Telling the LLM "this is for litigation mode, use neutral tone"
**Correct approach (mostly):** The writer pass SHOULD know about tone requirements (neutral vs analytical), but this is a quality gate concern, not a mode concern. The compliance pass already enforces tone. Add "neutral_tone" as a quality gate that is always-on (litigation readiness is a product-wide requirement per the constraints: "Must avoid subjective/emotional language -- withstand legal scrutiny").

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Methodology as pre-LLM Python | Deterministic, zero token cost, testable, auditable |
| Rules engine as pre-LLM Python | Explainable emphasis, traceable to named rules |
| Output modes as post-LLM filter | Single analysis run, 4 views -- cost and latency unchanged |
| New export file (not modify existing) | Clean interface, v1 fallback preserved |
| PipelineState extension (not new state) | Backwards compatible, incremental adoption |
| output_mode param on API endpoint | Minimal API change, frontend dropdown |

## Caching Implications

The existing Redis caching strategy (content-hash keys) extends naturally:

| Component | Cacheable? | Key Inputs | TTL Suggestion |
|-----------|-----------|------------|----------------|
| MethodologyResult | YES | EstimatePair content hash | Same as analysis (1hr) |
| SignalBundle | YES | category_rows + MethodologyResult hash | Same as analysis (1hr) |
| Analysis pass | YES (existing) | pair + deltas + methodology + signals | 1hr (existing) |
| Writer pass | YES (existing) | analysis result | 30min (existing) |
| Output mode filter | NO (fast, pure function) | -- | -- |
| XLSX export | NO (fast, deterministic) | -- | -- |

**Cache key change:** The analysis pass cache key must now include methodology and signals in its hash. This means v2.0 analyses will NOT hit v1.x cache entries, which is correct behavior (v2 analysis is richer).

## Open Questions

1. **Line item matching granularity:** The current system compares at category level via recaps. v2.0 requirements mention "line item matching logic improvements" and "unit cost comparison extraction." The full parser (`_run_parser_full`) already extracts line items with descriptions, quantities, units, and amounts. The question is: how granular should matching be? Fuzzy match on descriptions (rapidfuzz is already a dependency) or Xactimate activity code matching? This needs domain expert input.

2. **Output mode default:** Should the default mode be "Internal Estimator" (full depth, backwards compatible with v1) or "Executive" (the most common use case)? Recommendation: default to "Internal" for backwards compatibility, let users select.

3. **Methodology detection accuracy:** O&P detection from parsed data depends on parser extraction quality. If the parser misses O&P line items, methodology analysis will be wrong. This should be validated with real estimate pairs before relying on it for alert tags.

4. **Rule thresholds:** Initial thresholds (20% variance, $5,000 absolute delta, etc.) are educated guesses. These should be calibrated with real comparison data after deployment.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all files referenced above
- `src/pipeline/orchestrator.py` -- existing 3-pass pipeline structure
- `src/pipeline/state.py` -- PipelineState extension point
- `src/pipeline/models.py` -- Pydantic data contracts
- `src/bid_comp/core.py` -- BidComp.run() orchestration flow
- `src/bid_comp/export_xlsx.py` -- current XLSX export structure
- `src/tasks.py` -- worker integration and job flow
- `.planning/PROJECT.md` -- v2.0 requirements and constraints
- `.planning/codebase/ARCHITECTURE.md` -- existing architecture documentation

### Secondary (MEDIUM confidence)
- Build order rationale based on dependency analysis of component interfaces
- Caching strategy extension based on existing PipelineCache implementation

### Tertiary (LOW confidence)
- Rule threshold values (EMPH-01 at 20%, ALERT-02 at 15%) are starting guesses needing calibration
- Line item matching approach (fuzzy vs code-based) needs domain expert validation

## Metadata

**Confidence breakdown:**
- Pipeline integration architecture: HIGH -- derived directly from existing code structure
- Component boundaries: HIGH -- clear separation based on data dependencies
- Build order: HIGH -- determined by component dependency graph
- Data models: MEDIUM -- schemas are reasonable but will evolve during implementation
- Rule thresholds: LOW -- need real-world calibration

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable architecture, unlikely to change significantly)
