# Architecture Research: Multi-Pass LLM Pipeline

**Researched:** 2026-01-18
**Domain:** LLM pipeline orchestration for bid comparison narratives
**Confidence:** HIGH (patterns verified across multiple authoritative sources)

## Summary

The three-pass LLM pipeline (Analysis -> Writer -> Compliance Rewrite) should follow a **Sequential Agent** pattern with **explicit data contracts** between passes. Each pass operates on typed, validated data structures using Pydantic models, enabling clear boundaries, testability, and graceful degradation.

The current single-pass approach (sending 100k+ tokens in one prompt) creates timeout risk and monolithic failure modes. The multi-pass architecture reduces per-call token counts significantly (each pass receives only what it needs), enables caching of intermediate results, and allows conditional execution of the compliance rewrite pass.

**Primary recommendation:** Build three isolated pass functions sharing state through Pydantic models stored in a `PipelineState` container. Integrate with existing RQ worker by wrapping the pipeline in the existing `run_bid_comp_keys` task.

## Pipeline Structure

### Pass Isolation: Separate Functions, Shared State Container

Each pass is a pure function with typed inputs and outputs:

```
Pass 1 (Analysis)  : EstimatePair + TopDeltas  ->  AnalysisResult
Pass 2 (Writer)    : AnalysisResult + StyleGuide ->  DraftNarrative
Pass 3 (Compliance): DraftNarrative + QualityGates ->  FinalNarrative | DraftNarrative
```

**Pass isolation principle:** Each pass receives only the data it needs, not the full context. This:
1. Reduces token count per LLM call (addressing the 100k+ token timeout issue)
2. Enables independent testing of each pass
3. Allows caching at pass boundaries
4. Makes failure isolation straightforward

### Pipeline State Container

A single `PipelineState` dataclass holds all intermediate results:

```python
@dataclass
class PipelineState:
    # Inputs (from BidComp._build_pair existing flow)
    pair: EstimatePair
    top_deltas: List[Dict[str, Any]]

    # Pass 1 output
    analysis: Optional[AnalysisResult] = None

    # Pass 2 output
    draft: Optional[DraftNarrative] = None

    # Pass 3 output (or pass-through of draft if quality passed)
    final: Optional[FinalNarrative] = None

    # Quality gate results
    quality_report: Optional[QualityReport] = None

    # Pipeline metadata
    passes_executed: List[str] = field(default_factory=list)
    pass_timings_ms: Dict[str, int] = field(default_factory=dict)
    errors: List[PassError] = field(default_factory=list)
```

### Component Diagram

```
                            RQ Worker (existing)
                                   |
                                   v
                    +---------------------------+
                    |    run_bid_comp_keys      |
                    |  (existing entry point)   |
                    +---------------------------+
                                   |
         [EstimatePair, TopDeltas] |
                                   v
              +----------------------------------------+
              |        NarrativePipeline               |
              |  (new orchestrator, replaces          |
              |   BidComp._generate_narrative)         |
              +----------------------------------------+
                      |           |           |
                      v           v           v
              +-----------+ +-----------+ +-----------+
              | Analysis  | |  Writer   | |Compliance |
              |   Pass    | |   Pass    | |  Rewrite  |
              +-----------+ +-----------+ +-----------+
                      |           |           |
                      v           v           v
              [AnalysisResult] [DraftNarr] [FinalNarr]
                                           OR
                                      [DraftNarr if quality OK]
```

## Data Flow

### Pass 1: Analysis Pass

**Purpose:** Extract structured delta analysis with supporting line items. Produce analysis that can feed the writer without raw estimate JSON.

**Input:**
```python
class AnalysisInput(BaseModel):
    primary_name: str
    comparison_name: str
    primary_totals: Dict[str, float]  # category -> total
    comparison_totals: Dict[str, float]
    top_deltas: List[CategoryDelta]
    # Focused line item context (NOT full 100k JSON)
    primary_sample_items: Dict[str, List[LineItemSummary]]  # category -> items
    comparison_sample_items: Dict[str, List[LineItemSummary]]
```

**Output:**
```python
class AnalysisResult(BaseModel):
    category_analyses: List[CategoryAnalysis]  # For each top delta
    scope_gaps: List[str]  # Missing trades, allowances
    overall_delta_direction: Literal["primary_higher", "comparison_higher", "similar"]
    confidence: Literal["high", "medium", "low"]

class CategoryAnalysis(BaseModel):
    category: str
    primary_total: float
    comparison_total: float
    delta: float
    delta_drivers: List[str]  # "3 window units at $450/each missing"
    line_item_evidence: List[str]  # Specific items cited
```

**Token reduction:** Instead of 100k+ tokens (full JSON), this pass receives ~5-10k tokens (sampled line items per category).

### Pass 2: Writer Pass

**Purpose:** Generate adjuster-tone narratives from structured analysis. No access to raw data - only works from AnalysisResult.

**Input:**
```python
class WriterInput(BaseModel):
    analysis: AnalysisResult
    style_guide: StyleGuide  # Tone reference from PROJECT.md
    primary_name: str
    comparison_name: str
```

**Output:**
```python
class DraftNarrative(BaseModel):
    overview: str  # 2-3 sentences
    key_drivers: List[DriverNarrative]
    scope_observations: List[str]
    suggested_followups: List[str]

class DriverNarrative(BaseModel):
    category: str
    amounts: str  # "$12,500 vs $8,200"
    narrative: str  # "Delta driven by..."
```

**Token count:** ~2-3k tokens input (analysis is already summarized).

### Pass 3: Compliance Rewrite Pass (Conditional)

**Purpose:** Check quality gates. If pass, return draft unchanged. If fail, rewrite to fix issues.

**Input:**
```python
class ComplianceInput(BaseModel):
    draft: DraftNarrative
    quality_gates: QualityGates
    failed_checks: List[str]  # From deterministic quality check
```

**Output:** Either `DraftNarrative` (if quality passed) or `FinalNarrative` (rewritten).

## Conditional Execution

### Quality Gate Implementation

Quality checks are a mix of deterministic (measurable) and LLM-based (judgment):

```python
@dataclass
class QualityGates:
    # Deterministic checks (run before LLM compliance pass)
    max_soft_qualifiers: int = 3  # "suggests", "appears", "may indicate"
    max_sentences_per_trade: int = 2
    max_avg_words_per_sentence: int = 40
    max_bullet_words: int = 30
    max_total_bullets: int = 6

    # Patterns to detect
    hedging_phrases: List[str] = field(default_factory=lambda: [
        "suggests", "appears", "may indicate", "possibly", "seems to"
    ])
    analyst_phrases: List[str] = field(default_factory=lambda: [
        "it appears", "this suggests", "may be due to"
    ])

    # LLM judgment (only if deterministic passes)
    require_valuation_link: bool = True  # Every trade ties to $
```

### Conditional Flow

```python
def run_pipeline(state: PipelineState) -> PipelineState:
    # Pass 1: Always runs
    state.analysis = run_analysis_pass(state)
    state.passes_executed.append("analysis")

    # Pass 2: Always runs (needs analysis)
    state.draft = run_writer_pass(state)
    state.passes_executed.append("writer")

    # Quality check: Deterministic first
    quality_report = check_quality_deterministic(state.draft, state.quality_gates)
    state.quality_report = quality_report

    if quality_report.passed:
        # Skip compliance rewrite - draft becomes final
        state.final = state.draft
        state.passes_executed.append("compliance_skipped")
    else:
        # Pass 3: Conditional - only on quality failure
        state.final = run_compliance_pass(state, quality_report.failed_checks)
        state.passes_executed.append("compliance_rewrite")

    return state
```

### Quality Check Implementation

```python
def check_quality_deterministic(draft: DraftNarrative, gates: QualityGates) -> QualityReport:
    failed_checks = []

    # Hedging check
    hedging_count = count_hedging_phrases(draft.overview, gates.hedging_phrases)
    if hedging_count > gates.max_soft_qualifiers:
        failed_checks.append(f"hedging:{hedging_count} (max {gates.max_soft_qualifiers})")

    # Verbosity check per driver
    for driver in draft.key_drivers:
        sentences = count_sentences(driver.narrative)
        if sentences > gates.max_sentences_per_trade:
            failed_checks.append(f"verbose:{driver.category}:{sentences}s")

    # Analyst tone check
    for phrase in gates.analyst_phrases:
        if phrase.lower() in draft.overview.lower():
            failed_checks.append(f"analyst_tone:{phrase}")

    # Bullet length check
    for obs in draft.scope_observations:
        if len(obs.split()) > gates.max_bullet_words:
            failed_checks.append(f"bullet_length:{len(obs.split())}w")

    return QualityReport(
        passed=len(failed_checks) == 0,
        failed_checks=failed_checks,
        checked_at=datetime.utcnow()
    )
```

## Integration with Existing System

### Minimal Changes to Existing Code

The pipeline integrates at a single point: replace `BidComp._generate_narrative` with pipeline call.

**Current flow:**
```python
# BidComp.run() line ~285
narrative = self._generate_narrative(pair, top_deltas)
```

**New flow:**
```python
# BidComp.run()
pipeline = NarrativePipeline(self.llm_adapter, self.quality_gates)
narrative = pipeline.run(pair, top_deltas)
```

### RQ Worker Integration

No changes to `tasks.py` entry point. The pipeline runs inside `BidComp.run()` which is already called by `run_bid_comp_keys`.

```
run_bid_comp_keys (unchanged)
    -> BidComp(llm_adapter=...).run(bid_context, job_id)
        -> NarrativePipeline.run(pair, top_deltas)  # NEW
            -> analysis_pass()
            -> writer_pass()
            -> [conditional] compliance_pass()
        -> export_xlsx(narrative, ...)  # unchanged
```

### Timeout Mitigation

Current 180s timeout in `OpenAIChatAdapter` handles single large calls. With multi-pass:

| Pass | Estimated Tokens | Expected Time | Timeout Risk |
|------|-----------------|---------------|--------------|
| Current (single) | 100k+ | 2-3 min | HIGH |
| Analysis | 5-10k | 10-20s | LOW |
| Writer | 2-3k | 5-10s | LOW |
| Compliance | 2-3k | 5-10s | LOW |
| **Total** | 10-15k | 20-40s | LOW |

Per-pass timeout of 60s is safer than single 180s call.

### Error Handling

**Layered approach:**
1. **Retry with backoff** for transient failures (429, 5xx, timeout)
2. **Fallback** to previous pass output on pass failure
3. **Circuit breaker** if multiple passes fail consecutively

```python
class PassRunner:
    def run_with_resilience(
        self,
        pass_fn: Callable,
        state: PipelineState,
        fallback: Optional[Any] = None
    ) -> Any:
        for attempt in range(self.max_retries):
            try:
                return pass_fn(state)
            except RateLimitError:
                time.sleep(self.backoff_seconds * (2 ** attempt))
            except TimeoutError:
                if attempt == self.max_retries - 1:
                    self.circuit_breaker.record_failure()
                    return fallback
            except Exception as e:
                logger.warning(f"Pass failed: {e}")
                return fallback
        return fallback
```

**Fallback chain:**
- Analysis fails -> Use delta-only analysis (no line item detail)
- Writer fails -> Use template-based narrative
- Compliance fails -> Return draft as-is (quality check logged but not blocking)

## Caching Strategies

### Pass-Level Result Caching

Cache keyed by content hash of inputs:

```python
def cache_key(pass_name: str, inputs: BaseModel) -> str:
    content = inputs.model_dump_json(sort_keys=True)
    return f"pipeline:{pass_name}:{hashlib.sha256(content.encode()).hexdigest()}"
```

**Cache storage:** Redis (already used by RQ worker).

**TTL recommendations:**
- Analysis pass: 1 hour (estimates don't change once parsed)
- Writer pass: 30 min (style may be tweaked)
- Compliance pass: No cache (depends on quality gates which may change)

### What to Cache

| Pass | Cache? | Rationale |
|------|--------|-----------|
| Analysis | YES | Same estimates always produce same analysis |
| Writer | YES | Same analysis + style = same draft |
| Compliance | NO | Quality gates may change; small and fast anyway |

### Cache Implementation

```python
class PipelineCache:
    def __init__(self, redis: Redis, ttl_seconds: int = 3600):
        self.redis = redis
        self.ttl = ttl_seconds

    def get(self, key: str, model_cls: Type[BaseModel]) -> Optional[BaseModel]:
        data = self.redis.get(key)
        if data:
            return model_cls.model_validate_json(data)
        return None

    def set(self, key: str, result: BaseModel) -> None:
        self.redis.setex(key, self.ttl, result.model_dump_json())
```

### Embedding Caching (Future)

For analysis pass, cache embeddings of line item descriptions if semantic matching is added:
- Store embeddings in Redis or Qdrant (already integrated)
- Reuse across jobs for common line items
- Significant cost reduction for repeated item types

## Build Order

### Phase 1: Data Contracts (Foundation)

**Build first.** All passes depend on these types.

1. Define Pydantic models: `AnalysisResult`, `DraftNarrative`, `FinalNarrative`
2. Define `PipelineState` container
3. Define `QualityGates` and `QualityReport`
4. Unit tests for model validation

**Why first:** Types are the contracts between components. Changing them later requires updating all passes.

### Phase 2: Quality Gate (Deterministic Checks)

**Build second.** Required for conditional execution logic.

1. Implement `check_quality_deterministic()`
2. All measurable checks: hedging count, word counts, phrase detection
3. Tests with known-passing and known-failing narratives

**Why second:** Quality gate determines whether Pass 3 runs. Must be solid before pipeline orchestration.

### Phase 3: Analysis Pass

**Build third.** First LLM integration, simplest prompt.

1. Create analysis prompt template
2. Implement `run_analysis_pass()`
3. Add line item sampling logic (reduce 100k -> 10k tokens)
4. Structured output parsing with Pydantic
5. Integration test with real estimates

**Why third:** Analysis is the foundation data for all downstream passes.

### Phase 4: Writer Pass

**Build fourth.** Depends on Analysis pass output.

1. Create writer prompt template with adjuster tone examples
2. Implement `run_writer_pass()`
3. Map `AnalysisResult` -> writer prompt inputs
4. Parse output into `DraftNarrative`
5. Integration test: analysis -> writer

**Why fourth:** Writer consumes analysis, so analysis must work first.

### Phase 5: Pipeline Orchestration

**Build fifth.** Wire passes together.

1. Implement `NarrativePipeline` class
2. Conditional execution logic (skip compliance if quality passes)
3. Error handling and fallbacks per pass
4. Timing and logging per pass
5. Integration test: full pipeline end-to-end

**Why fifth:** Orchestration needs all components ready.

### Phase 6: Compliance Pass

**Build sixth.** Last pass, only runs on quality failure.

1. Create compliance rewrite prompt template
2. Implement `run_compliance_pass()`
3. Inject failed quality checks into prompt
4. Parse rewritten output
5. Integration test: quality fail -> compliance -> quality pass

**Why sixth:** Compliance is optional (quality may pass), so other passes have higher priority.

### Phase 7: Caching and Integration

**Build last.** Optimizations after core works.

1. Add Redis caching for Analysis and Writer passes
2. Replace `BidComp._generate_narrative` with pipeline call
3. End-to-end test through RQ worker
4. Performance comparison: single-pass vs multi-pass

**Why last:** Caching is an optimization, not a functional requirement.

## Dependencies and Integration Points

### Existing Components to Reuse

| Component | Location | Reuse |
|-----------|----------|-------|
| `OpenAIChatAdapter` | `src/llm/adapter.py` | Direct reuse for all LLM calls |
| `TemplateRegistry` | `src/llm/templates.py` | Add new prompt templates |
| `EstimatePair` | `src/bid_comp/core.py` | Input to pipeline |
| Redis connection | via `rq.job.Job` | Cache storage |
| Logging | `vip-parse.bid-comp` logger | Extend with pass-level logs |

### New Components to Create

| Component | Purpose | Location |
|-----------|---------|----------|
| `PipelineState` | State container | `src/pipeline/state.py` |
| Data contracts | Pydantic models | `src/pipeline/models.py` |
| `NarrativePipeline` | Orchestrator | `src/pipeline/orchestrator.py` |
| Pass functions | Individual passes | `src/pipeline/passes/` |
| Quality checker | Deterministic checks | `src/pipeline/quality.py` |
| Cache wrapper | Redis caching | `src/pipeline/cache.py` |

### New Prompt Templates

| Template ID | Purpose | System Prompt Focus |
|-------------|---------|---------------------|
| `analysis_pass_v1` | Extract deltas with evidence | "You are extracting structured comparison data" |
| `writer_pass_v1` | Generate adjuster-tone | "You write like a senior adjuster..." |
| `compliance_rewrite_v1` | Fix quality failures | "Rewrite to fix: {failed_checks}" |

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| Pipeline structure | HIGH | Sequential Agent pattern well-established; multiple sources confirm |
| Pass isolation | HIGH | Standard practice; matches existing modular design in codebase |
| Conditional execution | HIGH | Quality gates + skip pattern verified across evaluation frameworks |
| Error handling | HIGH | Retry/fallback/circuit-breaker pattern extensively documented |
| Caching strategy | MEDIUM | Redis caching straightforward; semantic caching more complex if added |
| Token reduction | HIGH | Sampling line items vs full JSON is proven approach |
| Build order | HIGH | Based on dependency analysis of codebase and pass relationships |
| Integration point | HIGH | `_generate_narrative` is clear replacement target |

## Open Questions

1. **LLM-based quality check for valuation links**: How to reliably detect if each trade narrative ties to financial impact? May need Pass 3 to always run with LLM judgment.

2. **Line item sampling strategy**: How many items per category is "enough" for analysis? Initial recommendation: top 5 by amount, but may need tuning.

3. **Style guide encoding**: Adjuster tone examples from PROJECT.md need to be formatted into writer prompt. Exact format TBD.

## Sources

### Primary (HIGH confidence)
- [Multi-Step LLM Chains Best Practices - DeepChecks](https://www.deepchecks.com/orchestrating-multi-step-llm-chains-best-practices/)
- [Retries, Fallbacks, Circuit Breakers - Portkey](https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/)
- [Quality Gates in LLM Pipelines - DeepWiki](https://deepwiki.com/strangeloopcanon/llm-hayek-roth/6.2-quality-gates-and-testing)
- [Pydantic for LLM Outputs](https://pydantic.dev/articles/llm-intro)
- [LLM Orchestration Patterns - orq.ai](https://orq.ai/blog/llm-orchestration)

### Secondary (MEDIUM confidence)
- [Google ADK Multi-Agent Patterns](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
- [5 Patterns for Scalable LLM Integration](https://latitude-blog.ghost.io/blog/5-patterns-for-scalable-llm-service-integration/)
- [Caching Strategies in LLM Services](https://www.rohan-paul.com/p/caching-strategies-in-llm-services)

### Codebase Analysis (HIGH confidence)
- `apps/vip-parse/src/bid_comp/core.py` - Current narrative generation flow
- `apps/vip-parse/src/llm/adapter.py` - LLM integration pattern
- `apps/vip-parse/src/tasks.py` - RQ worker integration point
- `apps/vip-parse/src/orchestrator/runners.py` - Existing DAG pattern (not used but informative)

---

*Research completed: 2026-01-18*
*Valid until: 30 days (stable patterns)*
