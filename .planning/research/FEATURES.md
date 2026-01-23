# Features Research: Professional Narrative Generation

**Researched:** 2026-01-18
**Domain:** Multi-pass LLM pipeline for style-controlled document generation
**Confidence:** HIGH for patterns, MEDIUM for specific implementations

## Summary

Professional document generation systems achieve style control through a combination of few-shot prompting with curated examples, explicit style guides in system prompts, and iterative refinement loops. Quality evaluation has moved beyond traditional metrics (BLEU/ROUGE) toward LLM-as-a-judge approaches using custom rubrics (G-Eval). For the VIP30 adjuster narrative use case, the research supports a multi-pass architecture with deterministic quality gates that can be implemented without fine-tuning.

**Primary recommendation:** Use few-shot prompting with 3-5 exemplar adjuster memos in the style pass, combined with rule-based validators for measurable criteria (hedging, word count, terminology) and G-Eval for subjective tone assessment.

---

## Style Control Patterns

### Few-Shot vs Fine-Tuning Decision

| Approach | When to Use | VIP30 Fit |
|----------|-------------|-----------|
| Few-shot prompting | Rapid iteration, prototype/MVP, style can be demonstrated via examples | HIGH - start here |
| Fine-tuning | High-stakes regulated output, deterministic requirements, scale justifies investment | MEDIUM - consider for v2.0 if few-shot insufficient |
| RAG with style corpus | Dynamic style adaptation, multi-brand scenarios | LOW - single style target |

**Research finding:** "Few-shot learning requires careful selection of examples... this significantly increases the required time investment" but "For MVPs, prototypes, or internal tools that need to be deployed quickly... Prompt design allows you to go live without any retraining overhead."

**VIP30 implication:** Few-shot with carefully curated adjuster memo examples is the correct starting point. Fine-tuning is premature optimization for v1.0.

### Few-Shot Example Selection

**Pattern: Demonstrate, Don't Describe**
- "If you need a tone that's 'professional yet approachable', showing examples of content that strikes this balance is far more effective than trying to explain it in words."
- Place examples after general instructions but before the specific task
- The LLM learns word choice, sentence structure, formality, pacing from examples

**VIP30 application:**
```
STYLE EXAMPLES (adjuster memo excerpts):

Example 1: "Large Delta on Estimate cost to Mitigate. Farmers allowed for $2,340 in PWI. Apex estimate includes $8,450 for mitigation - drives the $6,110 variance. Need itemized breakdown."

Example 2: "Apex fails to include MEP allowance. Farmers estimate: $14,200 MEP per unit. Apex does not contemplate mechanical/electrical work. Delta: $14,200 x 4 units = $56,800."

Example 3: "ELE scope mismatch. Carrier: panel upgrade + 12 circuits. Contractor: service upgrade only. Need ELE estimate clarification - possible scope exclusion."
```

### Style Pattern Recognition

**Key insight:** "Most teams treat brand voice as a 'vibe,' but for a language model, it is a set of statistically recognizable patterns."

For adjuster memos, the recognizable patterns are:
- **Sentence structure:** Short, declarative. No subordinate clauses hedging.
- **Word choice:** Industry abbreviations (PWI, MEP, ELE, PNT, SF), action verbs ("fails to include", "does not contemplate", "drives the variance")
- **Information density:** Numbers always present, tied to line items
- **Comparative framing:** "Carrier: X. Contractor: Y. Delta: Z."

### Terminology Handling

**Pattern: Glossary Injection via RAG**
- "LLMs can create inaccurate responses due to terminology confusion"
- "Lexical Retrieval Augmented Generation (LRAG) integrates source-text specific glossaries into LLM systems"

**VIP30 application:** Inject terminology glossary into system prompt:
```
TERMINOLOGY:
- PWI: Preliminary Water Investigation (mitigation/drying)
- MEP: Mechanical, Electrical, Plumbing
- ELE: Electrical
- PNT: Paint
- SF: Square Feet
- O&P: Overhead & Profit
```

This ensures consistent usage without custom tokenizers or fine-tuning.

---

## Quality Evaluation Approaches

### Metric Categories

| Category | Metrics | Implementation |
|----------|---------|----------------|
| **Deterministic** | Word count, sentence count, character limits | Regex/string ops |
| **Pattern-based** | Hedging words, banned phrases, terminology presence | Regex + word lists |
| **Semantic** | Tone, coherence, actionability | LLM-as-a-judge (G-Eval) |

### Hedging Detection (HIGH confidence)

**Research finding:** Hedge detection is a well-established NLP task with 80-84% accuracy using lexicon-based approaches.

**Hedge indicators for adjuster writing:**
- Modal verbs: "could", "might", "may", "would"
- Peacock expressions: "very likely", "I think", "perhaps"
- Weasel words: "some believe", "it appears", "seems to"
- Uncertainty markers: "possibly", "potentially", "probably"

**Implementation pattern:**
```python
HEDGE_WORDS = [
    "appears", "seems", "might", "may", "could", "possibly",
    "potentially", "suggests", "indicates", "perhaps", "likely",
    "probably", "apparently"
]

def count_hedges(text: str) -> int:
    text_lower = text.lower()
    return sum(1 for word in HEDGE_WORDS if word in text_lower)
```

**Quality gate:** Threshold of 3 or fewer hedge words per narrative section.

### Conciseness Metrics (HIGH confidence)

**Research finding:** "Conciseness refers to the ability of an LLM to be short and generate the least number of words without sacrificing accuracy."

**ConCISE metric approach:**
1. Compression ratio vs abstractive summary
2. Compression ratio vs extractive summary
3. Word-removal compression (how many non-essential words can be removed)

**Simpler deterministic approach for VIP30:**
- Sentence count per trade: max 2
- Average words per sentence: max 40
- Bullet length: max 30 words
- Total summary bullets: max 6

```python
def check_verbosity(text: str) -> dict:
    sentences = text.split('. ')
    word_counts = [len(s.split()) for s in sentences]
    return {
        "sentence_count": len(sentences),
        "avg_words_per_sentence": sum(word_counts) / len(word_counts) if word_counts else 0,
        "max_words": max(word_counts) if word_counts else 0,
        "passes": len(sentences) <= 2 and (sum(word_counts) / len(word_counts) if word_counts else 0) <= 40
    }
```

### Slop/GPT-ism Detection (MEDIUM confidence)

**Research finding:** "The Slop Score quantifies the frequency of 'GPT-isms'—overused phrases and tropes like 'tapestry,' 'delve,' or 'it's worth noting' that have become the hallmark of generic AI writing."

**EQ-Bench Slop Score composition:**
- 60% - Slop Words (unnaturally frequent in LLM output)
- 25% - "Not-x-but-y" patterns
- 15% - Slop Trigrams (3-word phrases overused by AI)

**VIP30 application:** Create adjuster-specific slop list:
```python
ANALYST_SLOP = [
    "it's worth noting", "delve", "tapestry", "landscape",
    "it is important to", "in conclusion", "significantly",
    "comprehensive", "holistic", "leverage", "synergy",
    "at the end of the day", "moving forward"
]
```

### Valuation Link Detection (MEDIUM confidence)

**Custom requirement:** Every trade section must tie to financial impact.

**Pattern:** Check for presence of dollar amounts or delta references:
```python
VALUATION_PATTERNS = [
    r'\$[\d,]+',           # Dollar amounts
    r'delta[:\s]+\$?[\d,]+',  # Explicit delta mentions
    r'variance[:\s]+\$?[\d,]+',
    r'difference[:\s]+\$?[\d,]+'
]
```

### G-Eval for Subjective Quality (HIGH confidence)

**Research finding:** "G-Eval is a framework that applies the LLM-as-a-Judge paradigm using a structured chain-of-thought (CoT) process to evaluate LLM outputs against any user-defined criteria."

**G-Eval components:**
1. Task Introduction
2. Evaluation Criteria (custom rubric)
3. Evaluation Steps (CoT reasoning)
4. Scoring function (0-1 continuous)

**VIP30 G-Eval rubric for tone:**
```
TASK: Evaluate whether this narrative matches professional adjuster memo style.

CRITERIA:
- Direct, declarative statements (not hedged or tentative)
- Uses industry terminology naturally (not explained or defined)
- Contains specific numbers tied to line items
- Includes actionable callouts where appropriate
- Uses comparative framing (Carrier vs Contractor)
- Avoids "analyst" language (no "suggests", "appears", "may indicate")

SCORING:
5 - Perfect adjuster tone, indistinguishable from human memo
4 - Strong adjuster tone with minor deviations
3 - Acceptable but noticeable AI patterns
2 - Clearly AI-generated, missing key style elements
1 - Generic AI output, no domain adaptation
```

---

## Multi-Pass Pipeline Patterns

### Self-Refine Architecture (HIGH confidence)

**Research finding:** "Self-Refine successively refines the output in a FEEDBACK -> REFINE -> FEEDBACK loop... outperforms direct generation from strong generators like GPT-3.5 and even GPT-4 by at least 5% to more than 40% improvement."

**Key limitation:** "State-of-the-art LMs show limited self-refinement gains (+1.8 percentage points or less) across five iterative attempts. In contrast, with guided feedback, models can achieve near-perfect performance (+80% gains)."

**Implication:** Self-critique alone is insufficient. External validation signals are required.

### VIP30 Pipeline Architecture

```
Pass 1: ANALYSIS (structured extraction)
  Input: Raw comparison data
  Output: JSON with category deltas, supporting line items, financial totals
  Validation: Schema validation, completeness check

Pass 2: WRITER (style-controlled generation)
  Input: Structured analysis + style examples + terminology glossary
  Output: Draft narrative in adjuster tone
  Validation: Deterministic quality gates

Pass 3: COMPLIANCE REWRITE (conditional)
  Trigger: Only if Pass 2 fails quality gates
  Input: Draft + specific failure reasons
  Output: Corrected narrative
  Validation: Re-run quality gates (max 2 iterations)
```

### Quality Gate Sequence

```
Gate 1: Hedging Check (deterministic)
  - Count hedge words
  - FAIL if > 3 per section
  - Feedback: "Remove hedging language: [specific words found]"

Gate 2: Verbosity Check (deterministic)
  - Sentence count, word averages
  - FAIL if > 2 sentences or avg > 40 words per trade
  - Feedback: "Reduce to 2 sentences max, under 40 words average"

Gate 3: Valuation Link (deterministic)
  - Check for dollar amounts or delta references
  - FAIL if trade section lacks financial tie
  - Feedback: "Add specific dollar amount or delta reference"

Gate 4: Terminology Check (deterministic)
  - Verify abbreviations used naturally
  - WARN if industry terms explained/defined
  - Feedback: "Use [term] directly without explanation"

Gate 5: Tone Assessment (G-Eval)
  - LLM-as-judge with rubric
  - FAIL if score < 3.5/5
  - Feedback: Specific rubric failures
```

---

## Table Stakes vs Differentiators

### Table Stakes (Must Have for Professional Quality)

| Feature | Complexity | Dependencies | Why Required |
|---------|------------|--------------|--------------|
| **Few-shot style examples** | LOW | None | Sets baseline tone without fine-tuning |
| **Terminology glossary injection** | LOW | None | Ensures consistent abbreviation usage |
| **Hedging word detection** | LOW | Regex | Measurable quality gate per project spec |
| **Sentence/word count limits** | LOW | String ops | Enforces brevity requirement |
| **Valuation link check** | LOW | Regex | Every trade must tie to dollars |
| **Multi-pass pipeline** | MEDIUM | Existing LLM adapter | Enables iterative refinement |
| **Conditional rewrite trigger** | MEDIUM | Quality gates | Avoids unnecessary LLM calls |

### Differentiators (What Makes Output Exceptional)

| Feature | Complexity | Dependencies | Why Exceptional |
|---------|------------|--------------|-----------------|
| **G-Eval tone scoring** | MEDIUM | Additional LLM call | Catches subjective quality issues deterministic checks miss |
| **Slop/GPT-ism detection** | MEDIUM | Custom word list | Eliminates AI-sounding phrases specific to LLM output |
| **Comparative framing enforcement** | MEDIUM | Pattern matching | Forces "Carrier: X. Contractor: Y." structure |
| **Action item extraction** | HIGH | Entity recognition | Auto-generates "Need X" callouts |
| **Line item citation** | HIGH | Data linkage | Every claim references specific estimate line |

### Feature Dependencies

```
                    ┌─────────────────────┐
                    │ Few-shot examples   │
                    │ (style baseline)    │
                    └─────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Hedging check   │ │ Verbosity check │ │ Valuation link  │
    │ (gate 1)        │ │ (gate 2)        │ │ (gate 3)        │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │ Conditional rewrite │
                    │ (pass 3 trigger)    │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ G-Eval tone scoring │
                    │ (final validation)  │
                    └─────────────────────┘
```

---

## Anti-Features (Deliberately Avoid)

### Fine-Tuning for v1.0
**Why avoid:** Premature optimization. Few-shot achieves similar results for style control without training infrastructure, model hosting, or data preparation overhead. Research indicates "prompt engineering allows you to go live without any retraining overhead."

**Risk if built:** 2-4 weeks additional development, ongoing model maintenance, harder to iterate on style.

### Custom Tokenizers
**Why avoid:** Domain-specific tokenizers are for cases where industry terms are incorrectly split. Standard tokenizers handle insurance abbreviations (PWI, MEP, ELE) correctly since they are uppercase letter sequences.

**Risk if built:** Complexity without benefit, incompatibility with hosted models.

### Reference-Based Metrics (BLEU/ROUGE)
**Why avoid:** "Traditional scorers like BLEU/ROUGE... semantic nuance in LLM outputs is not captured." No gold-standard reference exists for adjuster memos.

**Risk if built:** False confidence in metrics that do not correlate with professional quality.

### Self-Refinement Without External Signals
**Why avoid:** Research shows "LLMs show limited self-refinement gains (+1.8 percentage points)" without guided feedback. Pure self-critique leads to "self-bias—LLMs systematically overrate their own generations."

**Risk if built:** Wasted compute on iterations that do not improve quality.

### Unlimited Rewrite Loops
**Why avoid:** Diminishing returns after 2 iterations. "As model performance approaches its maximum potential, [iterative] strategy struggles to make further progress."

**Risk if built:** Latency spikes, API cost explosion, potential infinite loops on edge cases.

### Grammar/Spelling Focus
**Why avoid:** Modern LLMs rarely produce grammatical errors. Grammar checking adds latency without addressing the actual quality challenge (tone, style, domain fit).

**Risk if built:** Distraction from real quality problems.

### Sentiment Analysis for Tone
**Why avoid:** Sentiment (positive/negative/neutral) is not tone. Adjuster memos are neutral in sentiment but require specific stylistic patterns. Sentiment classifiers will not detect hedging, verbosity, or terminology issues.

**Risk if built:** False positives on acceptable content, false negatives on problematic patterns.

---

## Implementation Recommendations

### Phase 1: Foundation (1-2 days)
1. Create style example corpus (3-5 real adjuster memo excerpts)
2. Build terminology glossary JSON
3. Implement hedging word detector (regex)
4. Implement verbosity checker (word/sentence counts)

### Phase 2: Pipeline (2-3 days)
5. Create analysis pass prompt template
6. Create writer pass prompt template with few-shot examples
7. Wire quality gates between passes
8. Implement conditional rewrite trigger

### Phase 3: Refinement (2-3 days)
9. Build G-Eval rubric for tone assessment
10. Implement slop/GPT-ism detector
11. Add comparative framing validation
12. Create compliance rewrite prompt with specific feedback injection

### Metrics to Track
- Pass rate at each quality gate
- Rewrite trigger frequency
- G-Eval score distribution
- Latency per pass
- Total API cost per comparison

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Few-shot for style control | HIGH | Multiple authoritative sources agree, pattern well-established |
| Hedging detection | HIGH | Academic research with 80%+ accuracy, simple to implement |
| Verbosity metrics | HIGH | Deterministic calculation, clearly defined |
| G-Eval for LLM-as-judge | HIGH | Official documentation, widely adopted pattern |
| Self-Refine limitations | HIGH | Recent research (2025) with clear findings |
| Slop score approach | MEDIUM | Emerging pattern, less standardized |
| Multi-pass pipeline | MEDIUM | Established pattern but implementation varies |
| Terminology glossary via RAG | MEDIUM | Pattern documented but VIP30-specific application untested |

---

## Sources

### Primary (HIGH confidence)
- [SuperAnnotate: LLM Fine-Tuning in 2025](https://www.superannotate.com/blog/llm-fine-tuning) - few-shot vs fine-tuning decision framework
- [Confident AI: G-Eval Guide](https://www.confident-ai.com/blog/g-eval-the-definitive-guide) - LLM-as-judge implementation
- [Self-Refine Paper](https://selfrefine.info/) - iterative refinement patterns
- [ArXiv: Hedge Detection](https://arxiv.org/html/2405.13319v1) - hedging language classification
- [ArXiv: ConCISE Conciseness Metric](https://arxiv.org/html/2511.16846) - reference-free conciseness evaluation

### Secondary (MEDIUM confidence)
- [EQ-Bench: Slop Score](https://eqbench.com/slop-score.html) - GPT-ism detection methodology
- [Latitude: Style Consistency with Examples](https://latitude-blog.ghost.io/blog/how-examples-improve-llm-style-consistency/) - few-shot prompting patterns
- [IBM: Domain-Specific LLM](https://www.ibm.com/think/topics/domain-specific-llm) - terminology handling
- [LLM Guard: Regex Output Scanners](https://github.com/protectai/llm-guard/blob/main/docs/output_scanners/regex.md) - deterministic validation patterns

### Tertiary (LOW confidence, needs validation)
- Insurance adjuster documentation conventions - based on project context, not external research
- Specific threshold values (3 hedges, 40 words, etc.) - defined by project requirements, not industry standard

---

*Research complete. Output ready for /gsd:define-requirements consumption.*
