# Stack Research: Multi-Pass LLM Pipeline with Quality Gating

**Researched:** 2026-01-18
**Domain:** LLM pipeline orchestration, quality evaluation, style control
**Overall Confidence:** HIGH

## Executive Summary

For VIP30's three-pass narrative generation pipeline (analysis, writer, compliance rewrite), the research recommends **staying lightweight**: extend the existing OpenAI adapter with structured outputs rather than adopting a heavy framework like LangChain or DSPy. The quality gating requirements (hedging threshold, verbosity limits, tone detection) are best served by a combination of:

1. **DeepEval** for LLM-as-judge quality metrics with threshold gating
2. **textstat** for deterministic text statistics (sentence length, word count)
3. **Instructor** (optional) for Pydantic-validated structured outputs if the current manual JSON parsing becomes brittle

**Cost optimization strategy:** Use gpt-4o-mini for all passes (current model), only escalate to gpt-4o or gpt-4.1 if quality gates fail repeatedly. Expected cost: $0.15-0.60 per 1M tokens vs $2.50-10.00 for larger models.

---

## Recommended Stack

### Core: Keep Existing OpenAI Adapter Pattern

**Recommendation:** Do NOT adopt LangChain, DSPy, or LlamaIndex for this use case.

**Rationale:**
- The existing `OpenAIChatAdapter` in `src/llm/adapter.py` already handles the OpenAI API cleanly
- A three-pass pipeline with conditional third pass is simple sequential logic, not complex orchestration
- Frameworks add abstraction overhead without proportional benefit for deterministic pipelines
- DSPy's value is in prompt optimization across training runs; your prompts are fixed for v1.0
- LangChain's value is in tool/agent orchestration; this is pure text transformation

**What to build:**
```python
# Extend existing adapter with pass-specific methods
class NarrativePipeline:
    def __init__(self, adapter: OpenAIChatAdapter, evaluator: QualityEvaluator):
        self.adapter = adapter
        self.evaluator = evaluator

    def run(self, analysis_input: AnalysisInput) -> NarrativeResult:
        # Pass 1: Analysis (structured delta extraction)
        analysis = self.adapter.generate("narrative_analysis_v1", {...})

        # Pass 2: Writer (adjuster-tone generation)
        draft = self.adapter.generate("narrative_writer_v1", {...})

        # Pass 3: Quality gate check
        quality = self.evaluator.evaluate(draft)
        if not quality.passes_threshold:
            # Conditional compliance rewrite
            draft = self.adapter.generate("narrative_compliance_v1", {...})

        return NarrativeResult(draft, quality)
```

**Confidence:** HIGH - Verified by examining existing codebase architecture.

---

### Quality Gating: DeepEval

**Library:** `deepeval>=3.8.0`
**Current version:** 3.8.0 (released 2026-01-15)
**License:** Apache 2.0

**Why DeepEval:**
- Purpose-built for LLM output evaluation with threshold-based pass/fail
- Native Pytest integration fits existing test patterns
- Custom metrics API for domain-specific quality rules
- LLM-as-judge with reasoning (debuggable scores)
- CI/CD compatible out of the box

**What to use:**
| Quality Criterion | DeepEval Approach |
|-------------------|-------------------|
| Hedging threshold (<=3 soft qualifiers) | Custom deterministic metric (regex count) |
| Trade verbosity (<=2 sentences, avg <=40 words) | Custom deterministic metric (textstat) |
| Valuation link (every trade ties to financial impact) | Custom LLM-judge metric (G-Eval) |
| Summary length (bullets <=30 words, <=6 total) | Custom deterministic metric |
| Analyst tone detection | Custom LLM-judge metric (G-Eval) |

**Custom Metric Pattern:**
```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
import textstat

class HedgingMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5, max_hedges: int = 3):
        self.threshold = threshold
        self.max_hedges = max_hedges

    def measure(self, test_case: LLMTestCase) -> float:
        hedges = ["may", "might", "could", "possibly", "perhaps", "appears"]
        text = test_case.actual_output.lower()
        count = sum(text.count(h) for h in hedges)
        self.score = 1.0 if count <= self.max_hedges else 0.0
        self.reason = f"Found {count} hedge words (max: {self.max_hedges})"
        return self.score

    def is_successful(self) -> bool:
        return self.score >= self.threshold
```

**Cost implications:**
- Deterministic metrics (hedging, verbosity, length): Zero LLM cost
- LLM-judge metrics (valuation link, tone): ~$0.01-0.05 per evaluation using gpt-4o-mini
- Recommend: Run deterministic metrics first, only invoke LLM judge if deterministic pass

**Confidence:** HIGH - Verified via PyPI (v3.8.0) and official documentation.

---

### Text Statistics: textstat

**Library:** `textstat>=0.7.12`
**Current version:** 0.7.12 (released 2025-12-13)
**License:** MIT

**Why textstat:**
- Zero dependencies, fast execution
- Provides exactly what quality gates need: sentence count, word count, avg sentence length
- Deterministic (no LLM cost, no latency)
- Battle-tested for readability analysis

**Functions needed:**
```python
import textstat

# For trade verbosity check
textstat.sentence_count(text)      # Count sentences
textstat.lexicon_count(text)       # Word count
textstat.avg_sentence_length(text) # Average words per sentence

# For summary length check
def check_bullet_length(bullets: list[str], max_words: int = 30) -> bool:
    return all(textstat.lexicon_count(b) <= max_words for b in bullets)
```

**Confidence:** HIGH - Verified via PyPI (v0.7.12) and documentation.

---

### Structured Outputs: Instructor (Optional)

**Library:** `instructor>=1.14.0`
**Current version:** 1.14.4 (latest on PyPI)
**License:** MIT

**Current state:** The existing `BidComp` class already handles JSON parsing with `_coerce_structured_llm_output()` including fallbacks for Python-style quoting and code fence stripping.

**When to adopt Instructor:**
- If JSON parsing edge cases multiply (currently 3+ fallback strategies)
- If you need automatic retry on validation failure
- If adding Pydantic models for type safety improves developer experience

**If adopted:**
```python
import instructor
from pydantic import BaseModel

class NarrativeAnalysis(BaseModel):
    key_drivers: list[CostDriver]
    scope_gaps: list[str]
    overview: str

client = instructor.from_openai(OpenAI())
analysis = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=NarrativeAnalysis,
    messages=[{"role": "user", "content": prompt}]
)
# `analysis` is already a validated Pydantic model
```

**Recommendation:** Defer adoption unless JSON parsing becomes brittle. The existing implementation is working.

**Confidence:** MEDIUM - Library is stable, but adoption decision depends on observed brittleness.

---

### Model Selection & Cost Optimization

**Current model:** gpt-4o-mini ($0.15 input / $0.60 output per 1M tokens)

**Recommendation:** Stay with gpt-4o-mini for all three passes.

**Rationale:**
- Sufficient capability for structured text transformation
- 2.7x cheaper than gpt-4.1-mini ($0.40/$1.60)
- Quality issues should be addressed via prompt engineering, not model escalation
- Conditional third pass already provides a "retry" mechanism

**Model Cascading (if needed later):**
If quality gates fail persistently (>20% of requests), implement cascading:
```
Pass 1-2: gpt-4o-mini (fast, cheap)
Pass 3 (compliance): gpt-4o-mini first attempt
Pass 3 (retry): gpt-4o or gpt-4.1 if mini fails quality gate
```

**Cost comparison per 1M tokens:**
| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| gpt-4o-mini | $0.15 | $0.60 | Default for all passes |
| gpt-4.1-mini | $0.40 | $1.60 | Not recommended (no quality gain) |
| gpt-4o | $2.50 | $10.00 | Escalation target if needed |
| gpt-4.1 | $2.00 | $8.00 | Alternative escalation |

**Confidence:** HIGH - Pricing verified via OpenAI official pricing page (January 2026).

---

## Alternatives Considered

### LangChain / LangGraph

**What it is:** Popular orchestration framework for LLM applications with chains, agents, and memory.

**Why NOT for this use case:**
- Overkill for sequential three-pass pipeline
- Adds complexity without proportional value
- Learning curve for team
- Debugging through abstractions is harder than direct API calls
- Would require rewriting existing working adapter

**When it would make sense:**
- If pipeline needed dynamic tool selection
- If building conversational agents with memory
- If needing complex branching logic with many paths

**Confidence:** HIGH - Well-documented framework limitations for simple pipelines.

---

### DSPy

**What it is:** Stanford framework for "programming, not prompting" LLMs with automatic prompt optimization.

**Why NOT for this use case:**
- Value is in optimizing prompts across training examples
- Requires labeled training data to optimize
- Overkill when you have fixed, hand-crafted prompts
- Adds significant complexity for marginal gain on fixed pipelines

**When it would make sense:**
- If prompts need to be optimized automatically
- If building retrieval-augmented systems with tunable components
- If you have hundreds of labeled examples to train against

**DSPy results context:** Informal benchmarks show DSPy 2.5.29 raising GPT-4o-mini scores from 66% to 87% on complex reasoning tasks - but this requires the optimization loop and training data.

**Confidence:** HIGH - DSPy is powerful but wrong tool for deterministic text pipelines.

---

### RAGAS (vs DeepEval)

**What it is:** Lightweight RAG evaluation framework focused on retrieval quality.

**Why DeepEval instead:**
- RAGAS is optimized for RAG (retrieval + generation)
- VIP30 pipeline is pure generation (no retrieval component)
- DeepEval has richer custom metric support
- DeepEval provides score reasoning (debuggable)
- RAGAS metrics are not self-explaining

**Confidence:** HIGH - Both libraries verified; use case alignment favors DeepEval.

---

### Pydantic AI

**What it is:** Pydantic's official AI library for structured outputs and agent orchestration.

**Why Instructor instead (if needed):**
- Instructor is lighter, focused solely on structured extraction
- Pydantic AI is broader (agents, tracing, observability)
- For pure structured output, Instructor has simpler API
- Recommendation: Instructor for extraction, Pydantic AI for agents

**Confidence:** MEDIUM - Both are viable; Instructor is simpler for this scope.

---

## Integration Notes

### Fitting with Existing Architecture

The current codebase has clean separation:
- `src/llm/adapter.py`: OpenAI API wrapper
- `src/llm/templates.py`: Prompt template management
- `src/bid_comp/core.py`: Business logic using adapter

**Recommended integration pattern:**

```
src/
├── llm/
│   ├── adapter.py          # Existing, unchanged
│   ├── templates.py        # Add new templates for 3 passes
│   └── __init__.py
├── narrative/              # NEW module
│   ├── __init__.py
│   ├── pipeline.py         # Three-pass orchestration
│   ├── quality.py          # DeepEval metrics
│   └── models.py           # Pydantic models for structured output
├── bid_comp/
│   └── core.py             # Call narrative.pipeline instead of direct LLM
```

### Dependencies to Add

```txt
# Add to requirements.txt
deepeval>=3.8.0           # Quality gating
textstat>=0.7.12          # Text statistics
# instructor>=1.14.0      # Uncomment if JSON parsing becomes brittle
```

### Configuration

```python
# Quality gate thresholds (make configurable)
QUALITY_THRESHOLDS = {
    "max_hedge_words": 3,
    "max_sentences_per_trade": 2,
    "max_avg_words_per_sentence": 40,
    "max_bullet_words": 30,
    "max_summary_bullets": 6,
}
```

---

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| Keep existing adapter | HIGH | Examined codebase; works well for use case |
| DeepEval for quality | HIGH | PyPI verified v3.8.0; API matches requirements |
| textstat for statistics | HIGH | PyPI verified v0.7.12; simple, deterministic |
| gpt-4o-mini pricing | HIGH | Verified OpenAI pricing page Jan 2026 |
| Skip LangChain/DSPy | HIGH | Well-documented; overkill for sequential pipeline |
| Instructor optional | MEDIUM | Depends on observed JSON parsing issues |
| Model cascading | MEDIUM | Strategy is sound; implementation details TBD |

---

## Cost Projections

**Assumptions:**
- Average narrative request: ~2,000 input tokens, ~500 output tokens per pass
- Three passes per request (analysis, writer, conditional compliance)
- 80% of requests pass quality gate (no third pass needed)

**Per-request cost (gpt-4o-mini):**
```
Pass 1 (analysis):    2000 * $0.15/1M + 500 * $0.60/1M = $0.0006
Pass 2 (writer):      2000 * $0.15/1M + 500 * $0.60/1M = $0.0006
Pass 3 (20% of time): 2000 * $0.15/1M + 500 * $0.60/1M = $0.0006 * 0.2 = $0.00012

Average per request: ~$0.0013
Per 1,000 requests:  ~$1.30
Per 10,000 requests: ~$13.00
```

**Quality evaluation cost:**
- Deterministic metrics (hedging, verbosity): $0.00
- LLM-judge metrics (if used): ~$0.01-0.05 per evaluation

**Total estimated cost:** $1.50-2.00 per 1,000 narrative generations.

---

## Open Questions

1. **Quality gate calibration:** Thresholds (3 hedges, 40 words avg) need validation against real adjuster preferences. Plan A/B testing.

2. **Tone detection specifics:** "Analyst tone" needs precise definition. What words/patterns indicate analyst vs adjuster voice? May need domain expert input.

3. **Retry limits:** If compliance pass fails quality gate, what's the fallback? Return with warning? Escalate to human review?

4. **Caching opportunity:** If same estimate pair is processed multiple times, can analysis pass be cached? Would reduce costs by ~33%.

---

## Sources

### Primary (HIGH confidence)
- [OpenAI Pricing](https://openai.com/api/pricing/) - Model costs verified Jan 2026
- [DeepEval PyPI](https://pypi.org/project/deepeval/) - v3.8.0 released 2026-01-15
- [textstat PyPI](https://pypi.org/project/textstat/) - v0.7.12 released 2025-12-13
- [Instructor Documentation](https://python.useinstructor.com/) - Latest features and patterns

### Secondary (MEDIUM confidence)
- [DSPy vs LangChain Comparison (Qdrant)](https://qdrant.tech/blog/dspy-vs-langchain/) - Framework tradeoffs
- [DeepEval Custom Metrics Guide](https://deepeval.com/docs/metrics-custom) - Implementation patterns
- [LLM Cost Optimization Guide (FutureAGI)](https://futureagi.com/blogs/llm-cost-optimization-2025) - Cost strategies

### Tertiary (context only)
- [RAG Frameworks Comparison (AI Multiple)](https://research.aimultiple.com/rag-frameworks/) - Ecosystem overview
- [Model Cascading Research (arXiv)](https://arxiv.org/abs/2410.10347) - Theoretical foundation

---

## Metadata

**Research mode:** Stack (Ecosystem + Implementation)
**Research date:** 2026-01-18
**Valid until:** 2026-03-18 (60 days - stable ecosystem)
**Downstream consumer:** /gsd:create-roadmap for v1.0 milestone planning
