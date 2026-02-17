# Phase 11: Narrative Quality & Quality Gates - Research

**Researched:** 2026-02-17
**Domain:** Litigation-ready narrative quality enforcement, evidence grounding, insurance-domain language analysis
**Confidence:** HIGH

## Summary

Phase 11 transforms the existing 6-gate quality system into a 5-gate system purpose-built for litigation readiness. The existing gates (hedging, verbosity, valuation links, summary length, analyst tone, slop) must be reorganized and significantly expanded. Three entirely new gate types are needed: judgment language detection (GATE-02), quantification enforcement (GATE-03), evidence grounding (GATE-04), and methodology neutrality (GATE-05). The existing hedging gate (GATE-01) needs expansion from 13 generic words to ~80+ insurance-litigation-specific terms.

The key technical challenge is the evidence grounding gate (GATE-04). This gate must verify that narrative text does not reference data at finer granularity than what was actually parsed. The answer: implement this deterministically using the `DataProvenance.granularity` field from Phase 9's `MethodologyResult.data_granularity`. No LLM judge is needed. A deterministic checker can parse narrative sentences for entity references (specific line items, unit prices, quantities) and cross-reference against the `GranularityLevel` enum. If data is CATEGORY-level, any narrative mentioning specific line items, unit prices, or quantities fails the gate.

The writer pass prompt must be redesigned to produce evidence-based, quantified output by default. The compliance rewrite pass must be updated to address the new gate types. The existing `QualityEvaluator` architecture (list of checkers, aggregate pass/fail) is sound and should be extended, not replaced.

**Primary recommendation:** Extend the existing `quality.py` checker pattern with 5 new checker classes. Keep all gates deterministic (regex + pattern matching). Redesign the writer pass prompt to produce quantified, neutral output that passes gates on first attempt. Update compliance rewrite prompt with new gate vocabulary. Merge existing GATE-05 (AnalystToneChecker) and GATE-06 (SlopChecker) into the expanded GATE-01 (HedgingChecker) since they are all "prohibited language" detectors.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| re (stdlib) | - | Regex-based pattern matching for all 5 gates | Already used in existing quality.py. Deterministic, zero-dependency, fast |
| textstat | installed | Sentence counting for quantification enforcement (GATE-03) | Already used in VerbosityChecker. Reliable sentence boundary detection |
| pydantic | 2.11.9 (installed) | QualityCheckResult, QualityReport models | Already in use. Extends existing pipeline models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| enum (stdlib) | - | GranularityLevel for evidence grounding checks | Already defined in methodology/models.py |
| hashlib (stdlib) | - | Deterministic claim ID verification | Already used in DataProvenance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deterministic regex gates | LLM-as-judge for quality | LLM judge adds latency, cost, non-determinism. Regex gates run in <1ms, are 100% reproducible, and have zero false negatives for known patterns. Use regex. |
| Custom word lists | spaCy NER + POS tagging | Overkill. The domain has ~100 prohibited words/phrases. A flat list with regex `\b` word boundaries is faster and more predictable than NLP pipeline |
| textstat sentence counting | spaCy sentence tokenizer | spaCy is more accurate but adds ~200MB dependency. textstat is already installed and sufficient for sentence-level checks |

**Installation:**
```bash
# No new dependencies needed. All libraries already installed.
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  pipeline/
    quality.py             # Rewritten: 5 new checker classes + reorganized QualityEvaluator
    quality_words.py       # NEW: Centralized word/phrase lists (hedge words, judgment adjectives, methodology terms)
  prompts/
    writer_pass_v2.json    # NEW: Redesigned prompt for evidence-based quantified output
    compliance_rewrite_v2.json  # NEW: Updated for 5 gate types
```

### Pattern 1: Centralized Word Lists Module (quality_words.py)
**What:** Single source of truth for all prohibited words and phrases, organized by gate.
**When to use:** Every quality gate checker imports from this module.
**Example:**
```python
"""Centralized prohibited language lists for quality gates."""

# GATE-01: Hedge words — zero tolerance
# Sources: insurance litigation expert standards, Federal Rules of Evidence Rule 702
HEDGE_WORDS: list[str] = [
    # Generic hedging (from existing HedgingChecker)
    "appears", "seems", "might", "may", "could", "possibly", "potentially",
    "suggests", "indicates", "perhaps", "likely", "probably", "apparently",
    # Insurance-litigation-specific hedging
    "presumably", "arguably", "conceivably", "plausibly", "ostensibly",
    "purportedly", "allegedly", "supposedly", "roughly", "approximately",
    "estimated", "ballpark", "in the range of", "on the order of",
    # Speculative causation
    "may have caused", "could have resulted", "might be attributed",
    "possibly due to", "likely due to", "appears to be caused by",
    "seems to indicate", "suggests that", "may indicate",
    # Weak assertion
    "it would appear", "one might argue", "it could be said",
    "there is reason to believe", "it stands to reason",
    "in all likelihood", "for all intents and purposes",
    # Existing analyst phrases (merged from old GATE-05)
    "may indicate", "likely due to", "appears to be",
    "seems to suggest", "could potentially", "might be attributed to",
    "possibly due to", "suggests that", "this indicates that",
    "this suggests",
]

# GATE-01: GPT-isms — zero tolerance (merged from old GATE-06)
SLOP_PHRASES: list[str] = [
    "delve", "tapestry", "landscape", "comprehensive", "holistic",
    "leverage", "synergy", "significantly", "ultimately", "essentially",
    "arguably", "undoubtedly", "furthermore", "moreover", "nevertheless",
    "it's worth noting", "it is worth noting",
    "it is important to", "it's important to",
    "in conclusion", "at the end of the day",
    "moving forward", "in order to",
    "a testament to", "serves as a reminder",
    "a myriad of", "a plethora of",
    "dive into", "dive deep",
    "as we navigate", "navigating the",
]

# GATE-02: Judgment adjectives — zero tolerance
# These are evaluative words that take sides or imply one estimate is wrong
JUDGMENT_ADJECTIVES: list[str] = [
    # Value judgments on estimates
    "excessive", "inadequate", "inflated", "deflated",
    "unreasonable", "reasonable", "appropriate", "inappropriate",
    "sufficient", "insufficient", "overestimated", "underestimated",
    "overstated", "understated", "exaggerated", "minimized",
    # Quality judgments
    "thorough", "sloppy", "careless", "meticulous", "negligent",
    "comprehensive", "incomplete", "deficient", "superior", "inferior",
    # Correctness judgments
    "correct", "incorrect", "accurate", "inaccurate", "wrong", "right",
    "proper", "improper", "valid", "invalid", "legitimate", "illegitimate",
    # Necessity judgments
    "necessary", "unnecessary", "essential", "nonessential",
    "required", "unwarranted", "justified", "unjustified",
    # Fairness/reasonableness judgments
    "fair", "unfair", "generous", "stingy", "padded", "gutted",
    "bloated", "lean", "aggressive", "conservative",
    # Insurance-specific advocacy language
    "lowball", "lowballed", "shortchanged", "gouging", "price-gouging",
    "inflated pricing", "below market", "above market",
    "underscoped", "overscoped",
]

# GATE-02: Judgment phrases — zero tolerance
JUDGMENT_PHRASES: list[str] = [
    "fails to adequately", "does not properly",
    "should have included", "should not have included",
    "fails to account for", "neglects to include",
    "overlooks the need for", "ignores the requirement",
    "the correct approach", "the proper method",
    "industry standard requires", "best practices dictate",
    "any competent adjuster", "a reasonable adjuster would",
    "clearly demonstrates", "obviously shows",
    "full extent of necessary work",
    "fails to capture the true cost",
]

# GATE-05: Methodology neutrality — comparative adjectives and
# standard-referencing language prohibited in methodology sections
METHODOLOGY_PROHIBITED: list[str] = [
    # Comparative adjectives implying one methodology is better
    "better", "worse", "superior", "inferior",
    "more accurate", "less accurate",
    "more appropriate", "less appropriate",
    "more thorough", "less thorough",
    "more reliable", "less reliable",
    # Standard-referencing (implies one is wrong)
    "industry standard", "best practice", "accepted practice",
    "standard methodology", "proper methodology",
    "correct methodology", "appropriate methodology",
    "recognized approach", "preferred approach",
    "recommended approach",
    # Compliance language (implies non-compliance)
    "fails to comply", "does not meet standards",
    "non-compliant", "substandard",
    "below industry norms", "does not conform",
]
```

### Pattern 2: Judgment Language Checker (GATE-02)
**What:** Detects evaluative adjectives and advocacy phrases that take sides between estimates.
**When to use:** Applied to all narrative text (overview, key_drivers, scope_observations).
**Example:**
```python
class JudgmentLanguageChecker:
    """
    GATE-02: Detects evaluative adjectives and judgment phrases.

    These words/phrases take sides between estimates or imply one is
    wrong/inferior. They destroy neutrality and create litigation risk.

    Zero tolerance — any judgment word fails the check.
    """

    @property
    def check_name(self) -> str:
        return "GATE-02"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        found: list[str] = []
        text_lower = text.lower()

        # Check single-word judgments with word boundary
        for word in JUDGMENT_ADJECTIVES:
            pattern = rf'\b{re.escape(word.lower())}\b'
            if re.search(pattern, text_lower):
                found.append(word)

        # Check multi-word phrases
        for phrase in JUDGMENT_PHRASES:
            if phrase.lower() in text_lower:
                found.append(phrase)

        passed = len(found) <= max_violations
        details = (
            f"Found {len(found)} judgment terms: {found}"
            if found
            else "No judgment language found"
        )
        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details,
        )
```

### Pattern 3: Quantification Enforcement (GATE-03)
**What:** Every sentence that references a delta, difference, or variance must include both a dollar amount AND a percentage.
**When to use:** Applied to overview and key_driver narratives.
**Example:**
```python
class QuantificationChecker:
    """
    GATE-03: Enforces quantified language for every delta reference.

    Any sentence that references a difference between estimates must
    include both a dollar amount ($X,XXX) AND a percentage (X.X%).
    Sentences without delta references are exempt.
    """

    # Patterns that indicate a sentence references a delta/difference
    DELTA_INDICATORS = [
        r'\bdelta\b', r'\bdifference\b', r'\bvariance\b',
        r'\bhigher\b', r'\blower\b', r'\bmore\b', r'\bless\b',
        r'\bexceeds?\b', r'\bshortfall\b', r'\bgap\b',
        r'\bvs\.?\b', r'\bversus\b', r'\bcompared\b',
        r'\bgreater\b', r'\bsmaller\b',
    ]

    DOLLAR_PATTERN = re.compile(r'\$[\d,]+(?:\.\d{2})?')
    PERCENT_PATTERN = re.compile(r'\d+(?:\.\d+)?%')

    @property
    def check_name(self) -> str:
        return "GATE-03"

    def check(self, text: str) -> QualityCheckResult:
        sentences = self._split_sentences(text)
        violations: list[str] = []

        for sentence in sentences:
            if not self._references_delta(sentence):
                continue
            has_dollar = bool(self.DOLLAR_PATTERN.search(sentence))
            has_percent = bool(self.PERCENT_PATTERN.search(sentence))
            if not has_dollar or not has_percent:
                missing = []
                if not has_dollar:
                    missing.append("dollar amount")
                if not has_percent:
                    missing.append("percentage")
                violations.append(
                    f"Missing {', '.join(missing)}: '{sentence[:80]}...'"
                )

        passed = len(violations) == 0
        details = (
            f"{len(violations)} sentences missing quantification: {violations}"
            if violations
            else "All delta references include dollar amounts and percentages"
        )
        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details,
        )

    def _references_delta(self, sentence: str) -> bool:
        sentence_lower = sentence.lower()
        return any(
            re.search(pattern, sentence_lower)
            for pattern in self.DELTA_INDICATORS
        )

    def _split_sentences(self, text: str) -> list[str]:
        # Use textstat-compatible sentence splitting
        # Split on period, exclamation, question mark followed by space or end
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p.strip() for p in parts if p.strip()]
```

### Pattern 4: Evidence Grounding Checker (GATE-04)
**What:** Verifies narrative claims do not exceed the specificity of parsed input data. If data is at CATEGORY granularity, narrative must not reference specific line items, unit prices, or quantities.
**When to use:** Applied to all narrative text, using `MethodologyResult.data_granularity` from Phase 9.
**Example:**
```python
from src.methodology.models import GranularityLevel

class EvidenceGroundingChecker:
    """
    GATE-04: Evidence grounding — narrative cannot exceed data specificity.

    Uses DataProvenance.granularity to determine what level of detail
    the narrative is allowed to reference. If data_granularity is CATEGORY,
    the narrative must not mention specific line items, unit prices,
    individual quantities, or material specifications.

    Deterministic — no LLM judge needed. Pattern-matching only.
    """

    # Patterns that indicate line-item-level specificity
    # These should ONLY appear when granularity == LINE_ITEM
    LINE_ITEM_INDICATORS = [
        # Specific quantities with units
        r'\b\d+\s+(?:units?|pieces?|sheets?|rolls?|boxes?|bags?|gallons?|feet|SF|LF|SY|EA|HR)\b',
        # Unit pricing patterns
        r'\$[\d,]+(?:\.\d{2})?\s*(?:per|/)\s*(?:unit|SF|LF|SY|EA|HR|sq\s*ft|lin\s*ft)',
        r'(?:at|@)\s*\$[\d,]+(?:\.\d{2})?\s*(?:each|per|apiece)',
        # Specific material names with pricing (e.g., "14 impact windows at $1,800 each")
        r'\b\d+\s+\w+\s+(?:windows?|doors?|cabinets?|fixtures?|units?)\s+(?:at|@)\s*\$',
    ]

    # Patterns that indicate category-level claims (acceptable at CATEGORY+)
    CATEGORY_INDICATORS = [
        r'\bcategor(?:y|ies)\b',
        r'\btrade\b',
        r'\bsection\b',
        r'\btotal(?:s|ing)?\b',
    ]

    @property
    def check_name(self) -> str:
        return "GATE-04"

    def check(
        self,
        text: str,
        data_granularity: GranularityLevel,
    ) -> QualityCheckResult:
        """Check narrative text against data granularity level."""
        if data_granularity == GranularityLevel.LINE_ITEM:
            # Line-item granularity allows all references
            return QualityCheckResult(
                check_name=self.check_name,
                passed=True,
                details="Data granularity is LINE_ITEM; all references permitted",
            )

        # For CATEGORY, COVERAGE, or ESTIMATE_TOTAL, check for line-item references
        violations: list[str] = []
        for pattern in self.LINE_ITEM_INDICATORS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Line-item reference '{match}' found but data_granularity={data_granularity.value}"
                )

        passed = len(violations) == 0
        details = (
            f"{len(violations)} evidence grounding violations: {violations}"
            if violations
            else f"All claims within {data_granularity.value} granularity"
        )
        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details,
        )
```

### Pattern 5: Methodology Neutrality Checker (GATE-05)
**What:** Ensures methodology section contains no comparative adjectives or standard-referencing language.
**When to use:** Applied specifically to methodology-related narrative sections.
**Example:**
```python
class MethodologyNeutralityChecker:
    """
    GATE-05: Methodology neutrality — no comparative adjectives or
    standard-referencing in methodology sections.

    The methodology section describes HOW each estimate was constructed
    (O&P treatment, depreciation approach, pricing source). It must NOT
    imply one methodology is better, more correct, or more standard.

    Zero tolerance.
    """

    @property
    def check_name(self) -> str:
        return "GATE-05"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        found: list[str] = []
        text_lower = text.lower()

        for term in METHODOLOGY_PROHIBITED:
            term_lower = term.lower()
            if ' ' not in term:
                pattern = rf'\b{re.escape(term_lower)}\b'
                if re.search(pattern, text_lower):
                    found.append(term)
            else:
                if term_lower in text_lower:
                    found.append(term)

        passed = len(found) <= max_violations
        details = (
            f"Found {len(found)} methodology neutrality violations: {found}"
            if found
            else "Methodology section is neutral"
        )
        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details,
        )
```

### Pattern 6: Writer Pass Prompt v2 Structure
**What:** Redesigned prompt that produces quantified, neutral output by default, reducing compliance rewrite frequency.
**When to use:** Replaces writer_pass_v1.json.
**Key changes from v1:**
```
1. System prompt adds explicit QUANTIFICATION RULES:
   - Every sentence referencing a difference MUST include $amount AND %
   - Formula: "Category X: $A vs $B, a delta of $C (X.X%)"

2. System prompt adds EVIDENCE GROUNDING instruction:
   - "You may ONLY reference data at the granularity provided"
   - "If only category totals are available, do NOT reference specific
     line items, unit prices, or quantities"
   - Context variable: {data_granularity} injected into prompt

3. System prompt adds PROHIBITED LANGUAGE section:
   - Full hedge word list
   - Full judgment adjective list
   - Full methodology neutrality list
   - "If you use ANY of these words, the output will be rejected"

4. Few-shot examples rewritten to demonstrate quantified pattern:
   BAD:  "Primary includes significantly more electrical work"
   GOOD: "Electrical: Primary $12,500 vs Comparison $4,200, a delta of
          $8,300 (197.6%). Primary scopes full 200A panel upgrade with
          12 circuits; Comparison scopes service entrance repair only."

5. User prompt includes {data_granularity} and {available_evidence_fields}
   to ground the LLM's output in actual data availability
```

### Anti-Patterns to Avoid
- **LLM-as-judge for quality gates:** Adds latency (~2-5s), cost (~$0.01/check), and non-determinism. All 5 gates can be deterministic regex/pattern matching. Use LLM only for compliance REWRITING, never for quality CHECKING.
- **Single merged word list:** Keep hedge words, judgment adjectives, and methodology terms in separate lists. They serve different gates and have different scope (hedge words apply everywhere; methodology terms only apply to methodology sections).
- **Partial application of gates:** All 5 gates must run on every narrative. Do not skip gates for "performance." The entire check takes <10ms.
- **Hardcoded granularity in evidence grounding:** Always read `data_granularity` from `MethodologyResult`, never assume LINE_ITEM. The granularity varies per estimate pair.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sentence boundary detection | Custom regex sentence splitter | `textstat.sentence_count()` or `re.split(r'(?<=[.!?])\s+', text)` | Already in codebase via VerbosityChecker. Handles abbreviations ($1,234.56 won't split on the period) |
| Word boundary matching | Simple `in` operator for word detection | `re.compile(rf'\b{re.escape(word)}\b')` with `re.IGNORECASE` | Prevents false positives: "display" won't match "may", "category" won't match "or" |
| Dollar amount detection | Custom parsing | `re.compile(r'\$[\d,]+(?:\.\d{2})?')` | Already proven in existing ValuationLinkChecker. Handles commas and optional cents |
| Percentage detection | Custom parsing | `re.compile(r'\d+(?:\.\d+)?%')` | Simple, handles decimals |
| Quality gate aggregation | New aggregation logic | Extend existing `QualityEvaluator.evaluate()` pattern | Pattern proven: list of checkers, aggregate pass/fail, return QualityReport |
| Evidence grounding validation | LLM judge | Deterministic regex checking against `GranularityLevel` enum | LLM judge is overkill. The question is binary: "Does text reference line items when only categories exist?" Regex answers this in <1ms |

**Key insight:** Every quality gate in Phase 11 is deterministic. The domain has finite prohibited words (enumerable), finite quantification patterns (regex-matchable), and finite granularity levels (4 enum values). No NLP, no ML, no LLM judge needed.

## Common Pitfalls

### Pitfall 1: False Positives in Judgment Adjective Detection
**What goes wrong:** Words like "fair" match in "Fairfield" (a city name), "right" matches in "right-of-way", "complete" matches in "completed".
**Why it happens:** Naive substring matching without word boundaries or context.
**How to avoid:** Use `\b` word boundaries in regex. For known false positive patterns, add exclusion rules: `r'\b(?<!Fair)fair\b'` or maintain a small allowlist of compound words that contain judgment words but are neutral (e.g., "right-of-way", "Fairfield").
**Warning signs:** Quality gate fails on narratives that are actually neutral.

### Pitfall 2: Quantification Enforcement Catches Non-Delta Sentences
**What goes wrong:** Sentences like "Both estimates address the kitchen renovation" are flagged because they contain "both" but no dollar amount.
**Why it happens:** DELTA_INDICATORS are too broad, catching sentences that compare scope but not dollar amounts.
**How to avoid:** The delta indicator list must be specific to numerical comparisons, not scope descriptions. Include: "delta", "difference", "variance", "higher", "lower", "exceeds", "vs", "versus". Exclude: "both", "each", "addresses", "includes". Test against real narrative output to calibrate.
**Warning signs:** High false-positive rate on scope observation sentences.

### Pitfall 3: Evidence Grounding is Too Strict at Category Level
**What goes wrong:** Gate rejects all useful narrative content because CATEGORY granularity prohibits mentioning anything specific. Narratives become uselessly vague: "Category X totals differ."
**Why it happens:** LINE_ITEM_INDICATORS patterns are too aggressive, catching legitimate category-level descriptions like "roofing materials" or "electrical work".
**How to avoid:** Evidence grounding should prohibit FABRICATED specifics (invented unit prices, fake quantities, made-up material specs) but allow descriptive category references. The test is: "Does this claim require line-item data to verify?" If yes, and granularity is CATEGORY, reject. If no, allow.
**Warning signs:** Every narrative at CATEGORY granularity fails GATE-04 and gets rewritten into vague mush.

### Pitfall 4: Gate Renumbering Breaks Existing Tests
**What goes wrong:** Existing tests reference GATE-01 through GATE-06 by name. Renumbering gates changes all check_name strings.
**Why it happens:** Phase 11's GATE-01 through GATE-05 have different semantics than v1.0's GATE-01 through GATE-06.
**How to avoid:** Use semantic names in addition to gate numbers. In the new system: `check_name` is `"GATE-01-hedge"`, `"GATE-02-judgment"`, etc. Update all existing test assertions. Consider versioning: the old gates were `GATE-01-v1` through `GATE-06-v1`; new gates are `GATE-01-v2` through `GATE-05-v2`.
**Warning signs:** Test suite fails across the board after gate reorganization.

### Pitfall 5: Compliance Rewrite Loops on New Gates
**What goes wrong:** LLM removes hedge words (GATE-01) but introduces judgment adjectives (GATE-02) in the replacement text. Next iteration fixes GATE-02 but reintroduces hedging. Infinite loop within MAX_REWRITE_ITERATIONS.
**Why it happens:** Compliance rewrite prompt only addresses the specific failed gate, and the LLM's "fix" introduces violations in other gates.
**How to avoid:** The compliance rewrite prompt must include ALL prohibited word lists, not just the failed gate's list. The rewrite instruction should be: "Fix these specific failures AND ensure you do not use any words from these complete prohibited lists." Pass all 3 word lists (hedge, judgment, methodology) in every compliance rewrite.
**Warning signs:** Rewrites oscillate between gate failures, never converging. Both rewrite iterations fail.

### Pitfall 6: Writer Prompt v2 Gets Too Long
**What goes wrong:** Adding full word lists, quantification rules, evidence grounding instructions, and few-shot examples to the writer prompt pushes it past 8K tokens. Cost and latency increase.
**Why it happens:** The existing writer_pass_v1 system prompt is already ~3K tokens. Adding comprehensive prohibited lists doubles it.
**How to avoid:** Move prohibited word lists to a "reference" section at the end of the system prompt with a concise summary rule at the top: "CRITICAL: Your output will be checked against prohibited word lists. Do not use hedge words, judgment adjectives, or methodology comparison language. See REFERENCE SECTION for complete lists." The LLM respects this pattern. Also: the word lists in the prompt can be shorter (top 20 most common violations) with the full lists only in the deterministic gates.
**Warning signs:** LLM response quality degrades, or token budget is exceeded.

## Code Examples

Verified patterns from the existing codebase:

### Existing Quality Gate Pattern (extend, don't replace)
```python
# Source: src/pipeline/quality.py (existing pattern)
# Each checker has: check_name property, check() method returning QualityCheckResult
# QualityEvaluator aggregates all checks

class QualityEvaluator:
    def evaluate(self, draft: DraftNarrative) -> QualityReport:
        checks: List[QualityCheckResult] = []
        # Run each checker on appropriate text sections
        # ...
        passed = all(c.passed for c in checks)
        return QualityReport(passed=passed, checks=checks)
```

### Evidence Grounding: Reading Granularity from MethodologyResult
```python
# Source: src/methodology/models.py (existing from Phase 9)
# MethodologyResult.data_granularity is determined by MethodologyAnalyzer._determine_granularity()

class GranularityLevel(str, Enum):
    LINE_ITEM = "line_item"      # Specific items, prices, quantities available
    CATEGORY = "category"        # Only category totals (e.g., "Electrical: $12,500")
    COVERAGE = "coverage"        # Only coverage-level totals
    ESTIMATE_TOTAL = "total"     # Only grand total

# Evidence grounding gate uses this to decide what narrative can reference:
# LINE_ITEM -> can reference specific items, unit prices, quantities
# CATEGORY -> can reference category names and totals only
# COVERAGE -> can reference coverage types and totals only
# ESTIMATE_TOTAL -> can reference only the grand total
```

### Quantification Pattern for Writer Prompt
```python
# Pattern for key_driver narratives in writer_pass_v2:
# Every driver MUST follow this quantification structure:

# Template for amounts field:
# "{primary_name}: $X. {comparison_name}: $Y. Delta: $Z (XX.X%)"

# Template for narrative field (3 sentences):
# Sentence 1: What differs (scope/items) — include $ and %
# Sentence 2: Specifics from data (respecting granularity)
# Sentence 3: Neutral observation about methodology

# Example at CATEGORY granularity:
# amounts: "Apex Restoration: $12,500. Carrier Estimate: $4,200. Delta: $8,300 (197.6%)"
# narrative: "Electrical totals show a delta of $8,300 (197.6%) between Apex Restoration
#   and Carrier Estimate. Category-level data indicates Apex includes more electrical scope.
#   Both estimates use the same CALAW_FEB26 price list for unit cost basis."

# Example at LINE_ITEM granularity:
# amounts: "Apex Restoration: $12,500. Carrier Estimate: $4,200. Delta: $8,300 (197.6%)"
# narrative: "Apex Restoration includes a 200A panel upgrade (ELE PANEL+, $4,800) and 12 new
#   circuits ($640 each) not present in Carrier Estimate. Carrier scopes service entrance
#   repair only (ELE SERV &, $4,200). Delta of $8,300 (197.6%) driven by panel replacement
#   scope."
```

### Regex Patterns for Dollar and Percentage Detection
```python
# Proven patterns from existing ValuationLinkChecker + new additions

# Dollar amounts: $12,500 or $1,234.56
DOLLAR_RE = re.compile(r'\$[\d,]+(?:\.\d{2})?')

# Percentages: 12.5% or 200%
PERCENT_RE = re.compile(r'\d+(?:\.\d+)?%')

# Delta indicator words (trigger quantification requirement)
DELTA_WORDS_RE = re.compile(
    r'\b(?:delta|difference|variance|higher|lower|exceeds?|shortfall|'
    r'gap|vs\.?|versus|compared|greater|smaller|more than|less than)\b',
    re.IGNORECASE,
)

# Line-item specificity indicators (prohibited at CATEGORY granularity)
UNIT_PRICE_RE = re.compile(
    r'\$[\d,]+(?:\.\d{2})?\s*(?:per|/)\s*'
    r'(?:unit|SF|LF|SY|EA|HR|sq\s*ft|lin\s*ft|each)',
    re.IGNORECASE,
)
QUANTITY_UNIT_RE = re.compile(
    r'\b\d+\s+(?:units?|pieces?|sheets?|rolls?|boxes?|bags?|gallons?'
    r'|feet|SF|LF|SY|EA|HR|squares?|windows?|doors?|cabinets?)\b',
    re.IGNORECASE,
)
```

## State of the Art (current year)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic hedge word lists (13 words) | Domain-specific prohibited language (80+ terms across 3 categories) | This phase | Catches insurance-litigation-specific bias patterns the generic list misses |
| Valuation link check (has any $ reference) | Quantification enforcement (every delta sentence has $ AND %) | This phase | Ensures every claim is grounded in numbers, not qualitative language |
| No evidence grounding | Deterministic granularity-aware evidence grounding | This phase | Prevents LLM from fabricating line-item specifics when only category data exists |
| LLM-as-judge for quality (industry trend) | Deterministic regex gates | Deliberate choice | For a finite-domain problem (prohibited word lists), deterministic is faster, cheaper, and 100% reproducible |
| Post-hoc quality checking only | Pre-LLM prompt engineering + post-LLM deterministic checking | This phase | Writer prompt v2 produces output that passes gates on first attempt more often, reducing compliance rewrite frequency |

**New tools/patterns to consider:**
- Google DeepMind FACTS Grounding benchmark pattern: multi-judge consensus for factual grounding evaluation. Useful concept but overkill for this domain — our grounding check is binary (line-item reference vs category-level data) not open-ended factuality.
- Prompt debiasing via balanced exemplars and explicit bias instructions. Applicable: the writer prompt v2 should include explicit "DO NOT use these words" sections.

**Deprecated/outdated:**
- `max_hedges: int = 3` threshold from existing GATE-01. Zero tolerance is the new standard for litigation readiness.
- Separate AnalystToneChecker and SlopChecker classes. Merge into expanded HedgingChecker (GATE-01) since they all detect prohibited language.

## Open Questions

Things that could not be fully resolved:

1. **Evidence Grounding Edge Cases at CATEGORY Granularity**
   - What we know: When `data_granularity == CATEGORY`, the narrative should not reference specific line items. The gate uses regex to detect line-item-level language (unit prices, specific quantities, material names with prices).
   - What's unclear: Where exactly is the boundary? "Electrical work" is fine at CATEGORY level. "14 circuits" is not. But "roofing tear-off" (a process description, not a line item) is ambiguous. Does the LLM's general insurance knowledge count as "evidence" or is it fabrication?
   - Recommendation: Start conservative — only flag patterns that include specific numbers + units (e.g., "14 windows", "$450/each"). Descriptive process terms ("tear-off", "reglazing") are acceptable because they describe methodology, not specific line items. Calibrate with real output during testing.

2. **Quantification Enforcement for Scope Observations**
   - What we know: GATE-03 requires dollar amounts and percentages for every delta reference. Key_drivers always have amounts. Overview should have them.
   - What's unclear: Should scope_observations (bullet points about missing/different scope items) also require quantification? "Apex includes kitchen cabinets; Carrier estimate omits" doesn't naturally have a percentage.
   - Recommendation: Exempt scope_observations from GATE-03. They describe presence/absence, not magnitude. Apply GATE-03 only to `overview` and `key_drivers[].narrative`.

3. **Compliance Rewrite Convergence Rate**
   - What we know: Existing system allows MAX_REWRITE_ITERATIONS = 2. With 5 stricter gates, more rewrites may fail.
   - What's unclear: Will the LLM reliably fix all 5 gate types simultaneously? If not, do we need to increase MAX_REWRITE_ITERATIONS to 3?
   - Recommendation: Keep MAX_REWRITE_ITERATIONS = 2. Invest in writer prompt v2 quality so first-pass output rarely needs rewriting. If convergence is poor in testing, improve the writer prompt rather than adding rewrite iterations (each iteration costs ~$0.01 and ~3s latency).

## Sources

### Primary (HIGH confidence)
- **Codebase analysis** - Direct reading of `src/pipeline/quality.py` (existing 6 gates), `src/pipeline/models.py` (DraftNarrative, QualityCheckResult), `src/pipeline/orchestrator.py` (compliance loop), `src/pipeline/passes/writer.py`, `src/pipeline/passes/compliance.py`, `src/prompts/writer_pass_v1.json`, `src/prompts/compliance_rewrite_v1.json`, `src/methodology/models.py` (GranularityLevel, DataProvenance), `src/methodology/analyzer.py` (MethodologyAnalyzer)
- **Phase 9 Research** - `.planning/phases/09-data-foundation-methodology/09-RESEARCH.md` — DataProvenance pattern, GranularityLevel enum, evidence fabrication pitfall
- **REQUIREMENTS.md** - `.planning/REQUIREMENTS.md` — NARR-01 through NARR-03, GATE-01 through GATE-05 requirement definitions
- **Federal Rules of Evidence Rule 702** - Expert testimony reliability requirements (objectivity, verifiable evidence)
- **Google DeepMind FACTS Grounding** - https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/ — multi-judge grounding methodology (informed evidence grounding approach)

### Secondary (MEDIUM confidence)
- **Insurance expert witness report standards** - https://www.iqubedadvisors.com/blog/the-expert-witness-report-structure-content-and-how-it-strengthens-your-case-part-5/ — objectivity requirements, evidence-based analysis, bias avoidance
- **Property insurance appraisal bias** - https://www.propertyinsurancecoveragelaw.com/blog/insurance-company-engineering-report-bias/ — objectivity standards for insurance reports
- **Prompt debiasing research** - https://learnprompting.org/docs/reliability/debiasing — balanced exemplars, explicit bias instructions
- **Appraisal report language standards** - McKissock "Say This, Not That" (blocked by 403, but concept verified: appraisers must avoid subjective language and replace with fact-based descriptions)

### Tertiary (LOW confidence)
- **Insurance-litigation-specific hedge word list** - Compiled from training knowledge of Federal Rules of Civil Procedure Rule 26(a)(2) expert witness requirements, insurance bad faith litigation language patterns, and Xactimate estimate review standards. The specific word lists should be validated by a practicing insurance litigation attorney. The structure is sound; individual word inclusion may need calibration.
- **Judgment adjective categorization** - The division into value/quality/correctness/necessity/fairness categories is based on legal writing standards and insurance advocacy analysis. Specific words should be tested against real narrative output to confirm they cause false positives at acceptable rates.

## Metadata

**Confidence breakdown:**
- Gate architecture (extend existing QualityEvaluator): HIGH - Pattern proven in v1.0, clean extension
- Hedge word expansion: HIGH for structure, MEDIUM for specific word list - list needs calibration against real output
- Judgment adjective list: MEDIUM - comprehensive but may have false positives in edge cases
- Quantification enforcement: HIGH - regex patterns for $ and % are well-proven
- Evidence grounding approach: HIGH for architecture (deterministic + GranularityLevel), MEDIUM for specific regex patterns - edge cases at CATEGORY level need calibration
- Methodology neutrality: HIGH - simple prohibited word list applied to specific section
- Writer prompt v2 approach: HIGH - standard prompt engineering pattern (explicit constraints + few-shot examples)
- Word list completeness: LOW for insurance-litigation-specific terms - needs validation by domain expert

**Research date:** 2026-02-17
**Valid until:** 2026-04-17 (stable domain - insurance litigation standards evolve slowly, regex patterns don't expire)
