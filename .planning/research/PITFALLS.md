# Pitfalls Research: Multi-Pass LLM Pipeline

**Researched:** 2026-01-18
**Domain:** Three-pass LLM pipeline with quality gating for insurance claim narratives
**Confidence:** HIGH (multiple sources, verified patterns)

## Summary

Multi-pass LLM pipelines amplify costs, latency, and quality risks compared to single-pass approaches. The VIP30 three-pass design (analysis -> writer -> compliance rewrite) faces specific challenges: context explosion from serializing full estimate payloads, cascading quality drift between passes, over-correction from compliance rewrites, and unreliable quality gate thresholds.

This research identifies six critical pitfall categories with prevention strategies mapped to implementation phases. The existing timeout issue (100k+ tokens causing 180-second timeouts) and generic AI-sounding narratives are directly addressed.

---

## Token/Cost Pitfalls

### Pitfall 1: Context Payload Explosion

**What goes wrong:** Serializing full estimate payloads (`primary_json`, `comparison_json`) into each pass creates 3x token consumption. Current implementation already hits 100k+ tokens on large estimates causing timeouts.

**Why it happens:** The existing `BidComp._generate_narrative()` method passes entire estimate payloads as JSON strings:
```python
context = {
    "primary_json": json.dumps(pair.primary.payload, ensure_ascii=False),
    "comparison_json": json.dumps(pair.comparison.payload, ensure_ascii=False),
    ...
}
```
With three passes, this becomes 3x the current token load.

**Warning signs:**
- API calls exceeding 60 seconds (current timeout at 180s)
- Token counts in logs showing 50k+ prompt tokens
- Cost per comparison exceeding $0.50 on large estimates

**Prevention strategy:**
1. Analysis pass receives full payloads (unavoidable for extraction)
2. Writer pass receives only analysis output (structured deltas, not raw estimates)
3. Compliance pass receives only writer output (narrative text, not upstream data)
4. Each pass outputs compressed, targeted data for the next

**VIP30-specific:** Current `adapter.py` logs `prompt_bytes` and token counts. Add alerts when prompt_tokens > 50k.

**Cost projection:** With proper data flow isolation, three passes should cost ~1.5-2x single pass (not 3x) because downstream passes process smaller contexts.

**Phase mapping:** Phase 1 (Analysis Pass) must define output schema that minimizes downstream context.

---

### Pitfall 2: Redundant Compliance Pass Invocation

**What goes wrong:** Compliance rewrite runs on every comparison even when quality already passes, wasting tokens and adding latency.

**Why it happens:** Without short-circuit logic, the pipeline defaults to running all passes. Industry data shows well-tuned routing can skip unnecessary passes 70-85% of the time.

**Warning signs:**
- Compliance pass running when quality gates already pass
- Latency consistently at 3x single-pass baseline
- Cost scaling linearly with pass count instead of conditionally

**Prevention strategy:**
1. Quality gate runs immediately after writer pass
2. Compliance pass only triggers on gate failure
3. Log `pass_skipped=compliance` when quality passes
4. Track skip rate - target >70% of jobs skip compliance

**Phase mapping:** Phase 3 (Quality Gate) implements skip logic before compliance pass.

---

### Pitfall 3: Prompt Bloat in System Instructions

**What goes wrong:** Lengthy system prompts for tone/style eat context window before user content arrives. Research shows poor serialization consumes 40-70% of tokens through formatting overhead.

**Why it happens:** Complex adjuster-tone instructions and JSON schema examples inflate prompts. Each pass duplicates style guidance.

**Warning signs:**
- System prompt exceeding 2000 tokens
- Meaningful content pushed to context window edges ("lost in the middle" effect)
- Quality degradation on longer estimates despite shorter working

**Prevention strategy:**
1. System prompts under 1000 tokens per pass
2. Inline style examples, not exhaustive rules
3. Use JSON schema constraints in model, not verbose prose
4. Move tone reference to fine-tuning consideration (future)

**VIP30-specific:** Current `templates.py` prompts need audit for bloat. Adjuster tone reference should be 5-10 bullet examples, not paragraph descriptions.

**Phase mapping:** Phase 2 (Writer Pass) owns prompt efficiency for tone instructions.

---

## Quality Pitfalls

### Pitfall 4: Cascading Quality Drift Between Passes

**What goes wrong:** Each pass introduces small deviations that compound. Analysis extracts slightly wrong delta -> Writer amplifies error -> Compliance "fixes" by changing meaning.

**Why it happens:** LLM nondeterminism means output varies even with same input. When Pass N's output becomes Pass N+1's input, errors cascade. Research identifies this as the primary multi-pass reliability challenge.

**Warning signs:**
- Final narrative contradicts raw data
- Quality metrics oscillate (pass 2 passes, pass 3 fails quality check)
- "Corrected" narratives lose accurate information from earlier passes

**Prevention strategy:**
1. Analysis pass outputs structured data with explicit confidence flags
2. Writer pass receives delta data AND original source values for grounding
3. Each pass validates against known quantities (grand totals, delta values)
4. Add assertion: writer output delta values must match analysis output

**VIP30-specific:** The `_drivers_from_deltas()` already produces structured data. Ensure this anchors all downstream passes.

**Phase mapping:** All phases. Architecture decision: downstream passes receive source values for validation.

---

### Pitfall 5: Compliance Over-Correction

**What goes wrong:** Compliance rewrite changes content meaning while fixing style. "Farmers allowed $12,000 for roofing" becomes "The estimate includes roofing allowances" - losing specificity.

**Why it happens:** LLMs overcorrect when given style instructions. Research shows precision-recall tradeoff: prompts tuned for catching issues miss real content, prompts tuned for filtering false positives miss real issues.

**Warning signs:**
- Specific dollar amounts replaced with vague language
- Industry shorthand (PWI, MEP) removed or expanded incorrectly
- Post-compliance narratives longer but less informative
- Quality gate passes but output is generic

**Prevention strategy:**
1. Compliance prompt explicitly preserves: dollar amounts, category names, delta values, industry abbreviations
2. Use minimal-edit approach: "Fix only the specific issue flagged"
3. Compliance receives quality gate failure reason, not blanket "improve this"
4. Add post-compliance assertion: key quantities unchanged

**VIP30-specific:** Current AI-sounding output suggests over-smoothing. Compliance pass must be surgical, not wholesale rewrite.

**Research insight:** The PoCO approach (intentional overcorrection followed by precision pass) inverts this - consider if applicable.

**Phase mapping:** Phase 4 (Compliance Rewrite) must implement minimal-edit strategy.

---

### Pitfall 6: AI Tone Leakage

**What goes wrong:** Narratives sound like AI, not adjusters. "There appears to be a significant difference" instead of "Large Delta on Estimate cost to Mitigate."

**Why it happens:** LLMs default to hedged, formal language. Without strong style anchoring, outputs drift toward generic assistant voice. Current PROJECT.md already identifies this as the core problem.

**Warning signs:**
- "suggests", "appears", "may indicate", "potentially" in output
- Passive voice dominates
- Missing industry abbreviations
- Explanatory tone instead of declarative

**Prevention strategy:**
1. Writer pass receives 5-10 real adjuster examples (few-shot)
2. Quality gate explicitly checks for banned phrases
3. System prompt uses adjuster vocabulary in instructions themselves
4. Consider voice extraction: analyze real adjuster samples to build style profile

**VIP30-specific:** PROJECT.md adjuster tone reference is the source material. Quality gate criterion "analyst tone detection" directly addresses this.

**Phase mapping:** Phase 2 (Writer Pass) owns tone, Phase 3 (Quality Gate) enforces it.

---

## Performance Pitfalls

### Pitfall 7: Latency Stacking

**What goes wrong:** Three sequential API calls create 3x latency floor. Current 100k+ token requests already hit 60+ seconds; three passes could mean 3+ minute waits.

**Why it happens:** Multi-pass pipelines are inherently sequential - Pass 2 needs Pass 1 output. Unlike independent requests that can parallelize, passes must wait.

**Warning signs:**
- Total job duration > 120 seconds consistently
- User-perceived timeout (frontend polling gives up)
- Worker timeouts killing jobs mid-pipeline

**Prevention strategy:**
1. Optimize each pass independently before combining
2. Analysis pass targets structured output (faster than prose)
3. Compliance pass conditional (skip 70%+ of jobs)
4. Consider streaming for user feedback during long jobs
5. Timeout per pass (60s each) not just total

**VIP30-specific:** Current 180-second timeout in `adapter.py` must become per-pass budget. Consider increasing frontend polling patience.

**Async execution insight:** Research shows async patterns reduced RAG latency from 6-8 seconds to 2-3 seconds. Apply to independent operations (quality gate checks can run in parallel).

**Phase mapping:** Architecture phase (before Phase 1). Per-pass timeout strategy.

---

### Pitfall 8: Context Window Exhaustion on Large Estimates

**What goes wrong:** Large Xactimate estimates exceed model context limits even for single pass. Multi-pass makes this worse if each pass re-ingests full data.

**Why it happens:** Estimates with 200+ line items serialize to 100k+ characters. Model attention degrades at context edges ("lost in the middle" problem confirmed by research).

**Warning signs:**
- Missing categories in output despite presence in input
- Quality varies by estimate size (large = worse)
- Specific items mentioned early/late in estimate but not middle

**Prevention strategy:**
1. Pre-summarize large sections before LLM call
2. Analysis pass extracts then discards raw data
3. Chunk large estimates, aggregate results
4. Consider hierarchical summarization: sections -> categories -> totals

**VIP30-specific:** The `_build_summary_snapshot()` method already creates 10-item previews. Extend this pattern for LLM context.

**Research insight:** 400k+ characters triggers "expensive processing mode" with 50x latency increase. Stay well under.

**Phase mapping:** Phase 1 (Analysis Pass) must handle estimate size gracefully.

---

### Pitfall 9: Worker Timeout vs Pipeline Duration

**What goes wrong:** RQ worker timeout kills job partway through pipeline, leaving incomplete state.

**Why it happens:** Worker timeout configured for single-pass latency. Three passes exceed budget.

**Warning signs:**
- Jobs marked failed with timeout error
- Partial results in storage
- Inconsistent failure rates based on estimate size

**Prevention strategy:**
1. Set worker timeout to accommodate full pipeline (300s minimum)
2. Implement checkpoint/resume: save state between passes
3. Quality gate runs before longest pass (compliance) to fail fast
4. Consider separate queues with different timeout budgets

**VIP30-specific:** Check Render worker configuration. Current RQ setup may need adjustment.

**Phase mapping:** Architecture decision before Phase 1. Worker configuration.

---

## Evaluation Pitfalls

### Pitfall 10: Quality Gate Threshold Calibration

**What goes wrong:** Thresholds too strict = constant compliance rewrites (cost). Too loose = bad output passes (quality). Fixed thresholds don't adapt to content variation.

**Why it happens:** Quality metrics are heuristic. "3 soft qualifiers" may be appropriate for simple estimate, too many for complex. Binary pass/fail creates boundary instability.

**Warning signs:**
- Compliance pass triggered >50% of jobs (threshold too strict)
- User complaints despite quality gate passing (threshold too loose)
- Quality scores cluster at threshold boundary (calibration off)

**Prevention strategy:**
1. Use pass bands not single thresholds to avoid flakiness
2. Track distribution of scores, not just pass/fail
3. Calibrate thresholds against human-rated samples
4. Consider multiple violation = failure, not single

**VIP30-specific quality gates:**
- Hedging threshold (<=3 soft qualifiers): Consider 2-4 band
- Trade verbosity (<=2 sentences, avg <=40 words): May need per-trade adjustment
- Valuation link: Binary check, hard to miscalibrate
- Summary length (bullets <=30 words, <=6 total): Clear bounds
- Analyst tone: Pattern match on banned phrases

**Research insight:** Binary outputs produce more stable evaluations than numeric scoring.

**Phase mapping:** Phase 3 (Quality Gate) owns calibration. Requires baseline samples.

---

### Pitfall 11: LLM-as-Judge Self-Enhancement Bias

**What goes wrong:** Using same model to generate and judge creates bias. Model rates own output 5-7% higher than equivalent external content.

**Why it happens:** Model has implicit preferences that align with its own generation patterns. Judges tend toward self-favoring assessments.

**Warning signs:**
- Quality gate passes more often than human review suggests it should
- Pattern of "good enough" output that doesn't match user expectations
- Compliance pass rarely triggers despite visible quality issues

**Prevention strategy:**
1. Use different model for evaluation than generation (if budget allows)
2. Rely on deterministic checks where possible (word count, phrase detection)
3. Periodic human audit of passed outputs
4. Track user feedback as ground truth

**VIP30-specific:** Hedge detection and banned phrase lists are deterministic - prefer these over LLM judgment. Valuation link may need LLM evaluation.

**Phase mapping:** Phase 3 (Quality Gate). Implement deterministic checks first.

---

### Pitfall 12: False Negative Quality Gates (Missed Problems)

**What goes wrong:** Quality gate passes output that has real problems. User sees bad narrative despite "passing" quality check.

**Why it happens:** Metrics don't cover all quality dimensions. Hedging check passes but tone is wrong. Word count passes but content is wrong.

**Warning signs:**
- User complaints on jobs that passed quality gates
- Specific failure modes not captured by existing checks
- Gap between automated metrics and human assessment

**Prevention strategy:**
1. Start with comprehensive metric set, prune over time
2. Add new checks when failure patterns emerge
3. Maintain "golden set" of known-good/known-bad samples for regression
4. Quality gate failure reasons logged for pattern analysis

**VIP30-specific:** Current known issue is "AI-sounding narratives" - ensure analyst tone detection catches this specifically.

**Phase mapping:** Phase 3 (Quality Gate) with iteration based on production feedback.

---

## Implementation Pitfalls

### Pitfall 13: Generic Fallback Narrative Masking Failures

**What goes wrong:** When LLM fails, system returns generic narrative that looks like output but provides no value. Users can't distinguish failure from success.

**Why it happens:** Fallback logic prioritizes "returning something" over transparency. Current `_fallback_narrative()` returns template text.

**Warning signs:**
- Same narrative text appearing across different comparisons
- "Review manually" or similar in output
- Missing expected sections (cost drivers, observations)
- User confusion about whether comparison worked

**Prevention strategy:**
1. Fallback narratives clearly marked as incomplete
2. Include what succeeded vs failed
3. Consider failing loudly instead of silent degradation
4. Track fallback rate as KPI - target <5%

**VIP30-specific:** Current fallback includes "Narrative fallback: {reason}" but this may not surface to user clearly. Consider explicit error state.

**Phase mapping:** Error handling across all phases. Explicit failure signaling.

---

### Pitfall 14: Template/Prompt Drift

**What goes wrong:** Prompts edited over time without tracking. Changes improve one case, break another. No regression testing.

**Why it happens:** Prompt engineering is iterative. Without version control and evaluation sets, changes are blind.

**Warning signs:**
- "It used to work better"
- Different results from same input over time
- No clear record of prompt changes

**Prevention strategy:**
1. Version prompts explicitly (current `bid_comp_summary_v1` is good start)
2. Maintain evaluation set: input estimates + expected output characteristics
3. Run evaluation set before deploying prompt changes
4. Log prompt version with each generation for debugging

**VIP30-specific:** Current `TemplateRegistry` pattern supports versioning. Enforce version bumps on prompt changes.

**Phase mapping:** All phases. Testing infrastructure.

---

### Pitfall 15: Pass Coupling Through Implicit Contracts

**What goes wrong:** Pass 2 depends on Pass 1 output format, but format isn't enforced. Model drift or prompt change breaks downstream parsing.

**Why it happens:** LLM output is non-deterministic. Same prompt can produce different structures. Downstream passes assume structure that isn't guaranteed.

**Warning signs:**
- JSON parse errors between passes
- "KeyError" or missing field exceptions
- Inconsistent behavior based on input content

**Prevention strategy:**
1. Define explicit schema for each pass output
2. Validate output against schema before forwarding
3. Use structured output features (JSON mode, function calling)
4. Fallback/retry logic when structure validation fails

**VIP30-specific:** Current `_coerce_structured_llm_output()` handles some cases. Extend with explicit schema validation per pass.

**Phase mapping:** All phases. Schema definition in architecture.

---

## Prevention Strategies Summary

### Architectural Decisions (Before Phase 1)

| Decision | Purpose | Implementation |
|----------|---------|----------------|
| Per-pass timeout budget | Prevent pipeline timeout | 60s per pass, 240s total worker |
| Context isolation | Prevent token explosion | Each pass receives only what it needs |
| Schema contracts | Prevent pass coupling | JSON schema per pass output |
| Checkpoint capability | Enable resume on failure | State saved after each pass |

### Phase 1: Analysis Pass

| Pitfall | Prevention |
|---------|------------|
| Context explosion | Output compact schema, not raw estimates |
| Large estimate handling | Pre-summarize, chunk, or sample |
| Schema drift | Validate output structure |

### Phase 2: Writer Pass

| Pitfall | Prevention |
|---------|------------|
| AI tone leakage | Few-shot adjuster examples in prompt |
| Prompt bloat | <1000 token system prompt |
| Quality drift | Include delta values for grounding |

### Phase 3: Quality Gate

| Pitfall | Prevention |
|---------|------------|
| Threshold calibration | Pass bands, not single values |
| Self-enhancement bias | Deterministic checks where possible |
| False negatives | Comprehensive metric set, audit |
| Over-triggering | Target >70% compliance skip rate |

### Phase 4: Compliance Rewrite

| Pitfall | Prevention |
|---------|------------|
| Over-correction | Minimal-edit approach with preserved values |
| Redundant invocation | Only trigger on gate failure |
| Meaning loss | Post-compliance assertion on key values |

---

## Phase Mapping Reference

| Phase | Primary Pitfalls | Key Decisions |
|-------|------------------|---------------|
| Architecture | 7, 9, 15 | Timeout budget, schema contracts |
| Phase 1: Analysis | 1, 4, 8 | Output schema, context compression |
| Phase 2: Writer | 3, 6, 4 | Prompt efficiency, tone anchoring |
| Phase 3: Quality Gate | 10, 11, 12, 2 | Deterministic checks, skip logic |
| Phase 4: Compliance | 5, 2 | Minimal-edit, value preservation |
| All Phases | 13, 14 | Error handling, prompt versioning |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Token/Cost pitfalls | HIGH | Direct industry research, verified patterns |
| Quality drift | HIGH | Multiple sources confirm cascading effect |
| Over-correction | HIGH | Research literature on LLM overcorrection |
| Latency | HIGH | Sequential processing math + timeout data |
| Quality gate calibration | MEDIUM | Domain-specific thresholds need tuning |
| Self-enhancement bias | MEDIUM | Research shows 5-7% effect, magnitude varies |

---

## Sources

### Primary (HIGH confidence)
- [Kore.ai LLM Drift, Prompt Drift & Cascading](https://www.kore.ai/blog/llm-drift-prompt-drift-cascading) - cascading degradation patterns
- [RouteLLM Framework](https://lmsys.org/blog/2024-07-01-routellm/) - routing cost savings 45-85%
- [MLOps Community Prompt Bloat Impact](https://mlops.community/the-impact-of-prompt-bloat-on-llm-output-quality/) - prompt compression strategies
- [Evidently AI LLM-as-Judge](https://www.evidentlyai.com/llm-guide/llm-as-a-judge) - evaluation reliability

### Secondary (MEDIUM confidence)
- [arXiv LLM Overcorrection](https://arxiv.org/html/2509.20811v1) - PoCO approach for precision-recall
- [Medium Context Window Analysis](https://medium.com/@adityakamat007/understanding-llm-context-windows-why-400k-tokens-doesnt-mean-what-you-think-918704d04085) - 400k character threshold
- [Braintrust Evaluation Metrics](https://www.braintrust.dev/articles/llm-evaluation-metrics-guide) - quality gate thresholds
- [Scale Blog Voice Preservation](https://scale.com/blog/using-llms-while-preserving-your-voice) - tone consistency

### Tertiary (Project-specific)
- VIP30 `apps/vip-parse/src/llm/adapter.py` - current implementation patterns
- VIP30 `apps/vip-parse/src/bid_comp/core.py` - existing fallback and context handling
- VIP30 `.planning/PROJECT.md` - adjuster tone reference and requirements

---

## Metadata

**Research date:** 2026-01-18
**Valid until:** 60 days (patterns stable, thresholds may need tuning)
**Updates needed when:** Quality gate metrics established, production feedback available
