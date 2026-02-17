# Phase 9: Data Foundation & Methodology - Research

**Researched:** 2026-02-17
**Domain:** Insurance estimate comparison -- line-item matching, O&P/depreciation detection, structured LLM outputs, data provenance
**Confidence:** HIGH

## Summary

This phase adds a **pre-LLM enrichment layer** (MethodologyAnalyzer) that runs pure Python analysis on already-parsed Xactimate data, producing typed Pydantic models consumed by the existing 3-pass pipeline. The core domains are: (1) line-item matching between two estimates, (2) O&P structure detection, (3) depreciation methodology detection, (4) scope alignment matrix, (5) total delta breakdown, (6) data provenance tracking, and (7) migrating LLM calls to OpenAI Structured Outputs.

The existing codebase is well-positioned. The `HeuristicMatcher` in `src/bid_comp/matchers.py` already implements a 3-pass matching strategy (exact, alias, fuzzy via rapidfuzz WRatio). The Xactimate parser already extracts depreciation flags (`depreciate_material`, `depreciate_op`, `depreciate_non_material`, `depreciate_taxes`, `depreciate_removal`), O&P group taxonomy, ACV/RCV values from coverage tables, and line-item activity codes (CAT/SEL/ACT). The work is assembling these into typed MethodologyResult and enriching the PipelineState.

**Primary recommendation:** Extend `HeuristicMatcher` to support Xactimate activity codes as Pass 0 (before exact/alias/fuzzy), build a `MethodologyAnalyzer` class that produces `MethodologyResult` and `ScopeAlignmentMatrix` Pydantic models from already-parsed data, add `DataProvenance` tracking to every analytical claim, and migrate the LLM adapter from raw JSON parsing to `client.beta.chat.completions.parse()` with Pydantic response models.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rapidfuzz | 3.9.7 (installed) | Fuzzy string matching for line-item descriptions | Already in use. C++ core, 20-100x faster than fuzzywuzzy, MIT license |
| pydantic | 2.11.9 (installed) | Typed data models for all analysis outputs | Already in use. Required by OpenAI SDK. Validates all pipeline state |
| openai | 1.108.0 (installed) | LLM calls with Structured Outputs | Already installed. Version 1.108.0 fully supports `beta.chat.completions.parse()` |
| openpyxl | installed | XLSX export (downstream) | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib (stdlib) | - | Deterministic hashing for provenance IDs | Every analytical claim needs a stable ID |
| enum (stdlib) | - | Granularity levels, O&P structure types | Type-safe enumeration of known states |
| re (stdlib) | - | Xactimate activity code parsing | Already used extensively in parser |
| functools (stdlib) | - | `@lru_cache` for deterministic memoization | Caching methodology results for DATA-06 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rapidfuzz WRatio | thefuzz (fuzzywuzzy) | rapidfuzz is 20-100x faster, already installed. No reason to switch |
| Custom activity code matcher | Embedding-based similarity | Overkill. Xactimate codes are structured (CAT+SEL+ACT). Exact match on codes then fuzzy on descriptions is sufficient |
| Manual JSON parsing of LLM output | OpenAI Structured Outputs | Structured Outputs guarantees schema compliance. Eliminates entire class of parse failures |

**Installation:**
```bash
# No new dependencies needed. All libraries already installed.
# Only change: update openai SDK usage from create() to parse()
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  methodology/
    __init__.py           # Public API: MethodologyAnalyzer
    analyzer.py           # Main MethodologyAnalyzer class
    models.py             # Pydantic models: MethodologyResult, OPStructure, DepreciationMethod, etc.
    line_matcher.py       # Extended line-item matching (activity code + description)
    op_detector.py        # O&P structure detection from parsed data
    depreciation.py       # Depreciation methodology detection
    scope_alignment.py    # Scope alignment matrix builder
    provenance.py         # DataProvenance tracking
  pipeline/
    state.py              # Extended PipelineState with Optional[MethodologyResult]
    structured_adapter.py # New: OpenAI Structured Outputs adapter wrapping existing LLMAdapterBase
```

### Pattern 1: MethodologyAnalyzer as Pre-LLM Enrichment
**What:** Pure Python class that analyzes two parsed estimates and produces typed results BEFORE any LLM call.
**When to use:** Always -- runs between PDF parsing and LLM pipeline.
**Example:**
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

class GranularityLevel(str, Enum):
    LINE_ITEM = "line_item"      # Individual line items available
    CATEGORY = "category"        # Only category totals available
    COVERAGE = "coverage"        # Only coverage-level totals
    ESTIMATE_TOTAL = "total"     # Only grand total available

class DataProvenance(BaseModel):
    """Every analytical claim must carry provenance."""
    claim_id: str = Field(description="Deterministic hash of claim content")
    source_estimate: Literal["primary", "comparison"]
    granularity: GranularityLevel
    source_field: str = Field(description="JSON path to source data, e.g. 'sections[2].line_items[5].total'")
    raw_value: str = Field(description="Exact value from parsed data")

class OPStructure(BaseModel):
    has_general_op: bool
    general_op_pct: Optional[float] = None
    has_per_line_op: bool
    op_items_total: Optional[float] = None
    non_op_items_total: Optional[float] = None
    overhead_total: Optional[float] = None
    profit_total: Optional[float] = None
    depreciate_op: Optional[bool] = None
    provenance: List[DataProvenance] = Field(default_factory=list)

class DepreciationMethodology(BaseModel):
    is_acv: bool = Field(description="True if ACV policy, False if RCV")
    depreciate_material: Optional[bool] = None
    depreciate_non_material: Optional[bool] = None
    depreciate_taxes: Optional[bool] = None
    depreciate_removal: Optional[bool] = None
    depreciate_op: Optional[bool] = None
    price_list: Optional[str] = None
    provenance: List[DataProvenance] = Field(default_factory=list)

class MethodologyResult(BaseModel):
    primary_op: OPStructure
    comparison_op: OPStructure
    primary_depreciation: DepreciationMethodology
    comparison_depreciation: DepreciationMethodology
    op_treatment_differs: bool
    depreciation_approach_differs: bool
    price_list_differs: bool
    locality_factors: Optional[str] = None
```

### Pattern 2: Activity Code Matching (Pass 0 in HeuristicMatcher)
**What:** Match line items by Xactimate activity code (CAT+SEL+ACT) before falling back to description matching.
**When to use:** When both estimates are Xactimate rough drafts with parsed activity codes.
**Example:**
```python
# Xactimate activity code format: CAT=3-letter, SEL=variable, ACT=single char
# Example from parser: CAT="PNT", SEL="DRYWALL", ACT="+"
# Full code: "PNT DRYWALL +"

# Pass 0: Match by full activity code (CAT+SEL+ACT) -- exact identity
# Pass 1: Match by CAT+SEL (ignore activity) -- same item, different action
# Pass 2: Existing exact label match
# Pass 3: Existing alias match
# Pass 4: Existing fuzzy match (WRatio >= 0.90)

class LineItemMatch(BaseModel):
    primary_idx: int
    comparison_idx: Optional[int] = None
    match_method: Literal["activity_code", "cat_sel", "exact", "alias", "fuzzy", "unmatched"]
    match_score: Optional[float] = None
    primary_description: str
    comparison_description: Optional[str] = None
    primary_amount: Optional[float] = None
    comparison_amount: Optional[float] = None
    delta: Optional[float] = None
    provenance: DataProvenance
```

### Pattern 3: OpenAI Structured Outputs Migration
**What:** Replace `client.chat.completions.create()` + manual JSON parsing with `client.beta.chat.completions.parse()` + Pydantic models.
**When to use:** Every LLM call in the pipeline.
**Example:**
```python
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Literal

# Define response model
class CategoryAnalysisResponse(BaseModel):
    category_analyses: List[CategoryAnalysis]
    scope_gaps: List[str]
    overall_delta_direction: Literal["primary_higher", "comparison_higher", "similar"]
    confidence: Literal["high", "medium", "low"]

# Use parse() instead of create()
client = OpenAI()

completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    response_format=CategoryAnalysisResponse,
)

# Parsed Pydantic model -- no JSON parsing needed
result: CategoryAnalysisResponse = completion.choices[0].message.parsed
```

### Pattern 4: PipelineState Extension with Backward Compatibility
**What:** Add Optional fields to PipelineState so existing pipeline works without methodology analysis.
**When to use:** Extending PipelineState for new pre-LLM data.
**Example:**
```python
class PipelineState(BaseModel):
    # ... existing fields ...

    # Phase 9 additions (Optional for backward compat)
    methodology: Optional[MethodologyResult] = Field(
        default=None,
        description="Pre-LLM methodology comparison (O&P, depreciation, pricing)"
    )
    scope_alignment: Optional[ScopeAlignmentMatrix] = Field(
        default=None,
        description="Line-item scope alignment between estimates"
    )
    line_matches: Optional[List[LineItemMatch]] = Field(
        default=None,
        description="Line-item matching results"
    )
    delta_breakdown: Optional[DeltaBreakdown] = Field(
        default=None,
        description="Total delta with category breakdown sorted by magnitude"
    )
```

### Anti-Patterns to Avoid
- **Sending raw line items to LLM for matching:** Line-item matching is a deterministic problem. Use activity codes and fuzzy matching. LLM is for narrative, not data alignment.
- **Parsing LLM JSON output with regex/json.loads:** Use OpenAI Structured Outputs. The SDK guarantees valid Pydantic models.
- **Optional provenance:** Every DataProvenance field must be required, not optional. If you can't prove where data came from, don't include the claim.
- **Mutable global state in MethodologyAnalyzer:** Keep it functional -- inputs in, typed outputs out. No side effects.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein implementation | `rapidfuzz.fuzz.WRatio` + `rapidfuzz.process.extractOne` | Already in codebase, C++ optimized, handles edge cases (empty strings, Unicode) |
| JSON schema validation for LLM output | Try/except JSON parsing with fallbacks | `client.beta.chat.completions.parse(response_format=PydanticModel)` | Guaranteed schema compliance from OpenAI API. Zero parsing failures |
| Pydantic model serialization/hashing | Custom `__hash__` or `json.dumps` | `model.model_dump_json()` + `hashlib.sha256` | Pydantic handles all serialization edge cases |
| O&P group name normalization | Fresh alias mapping | Existing `taxonomy.py` `canonicalize_group()` + `GROUP_ALIASES` | Already handles O&P, NON-O&P, OVERHEAD, PROFIT variants |
| Label normalization | Custom string cleaning | Existing `normalize.py` `normalize_label()` | Already handles Unicode dashes, whitespace, case |
| Activity code category lookup | Hard-coded mapping | Parser already extracts CAT/SEL/ACT from line items via `LINE_ITEM_PATTERN` | Regex-based extraction in constants.py already works |

**Key insight:** The Xactimate parser already extracts 90% of the data needed for methodology analysis. The work is assembling extracted fields into typed Pydantic models, not building new extraction logic.

## Common Pitfalls

### Pitfall 1: LLM Fabricating Line-Item Evidence (P-04)
**What goes wrong:** LLM claims "Primary includes 3 windows at $450/each" when only category totals are available. The LLM invents specific line items that don't exist in the parsed data.
**Why it happens:** When parsed data only has category-level totals (no line items), the LLM fills in plausible-sounding but fabricated evidence.
**How to avoid:** Enforce `GranularityLevel` on every analytical claim. If `granularity == "category"`, the MethodologyAnalyzer must NOT produce line-item-level claims. The LLM prompt must include granularity context: "Only category totals available for this section. Do not reference specific line items."
**Warning signs:** Narrative mentions specific quantities, unit prices, or item descriptions that don't appear in `sections[].line_items[]`.

### Pitfall 2: Activity Code Availability Varies
**What goes wrong:** Code assumes all estimates have CAT/SEL/ACT codes. Final Draft format PDFs use Layout A (DESCRIPTION/QUANTITY/UNIT/PRICE/TAX/RCV) which does NOT include activity codes.
**Why it happens:** Only Rough Draft format (Layout B) includes the CAT/SEL/ACT columns. Final Draft format has descriptions but no codes.
**How to avoid:** Check which layout was parsed. If Layout A (no activity codes), skip activity code matching and go straight to description-based fuzzy matching. The `TableColumns.headers_norm` field tells you which layout: if it contains "CAT", "SEL", "ACT" it's Layout B.
**Warning signs:** `match_method` is "activity_code" but the parsed data has no CAT/SEL/ACT columns.

### Pitfall 3: O&P Can Be Structured Multiple Ways
**What goes wrong:** Code assumes O&P is always a single percentage applied to the total. In reality, Xactimate supports: (a) general O&P as percentage of total, (b) per-line-item O&P flags, (c) separate "O&P Items" vs "Non-O&P Items" groupings, (d) cumulated vs non-cumulated O&P.
**Why it happens:** Different adjusters configure O&P differently in Xactimate parameters.
**How to avoid:** Detect O&P structure from multiple signals:
  - `taxonomy.py` already has "O&P ITEMS" and "NON-O&P ITEMS" canonical groups
  - Parser extracts `depreciate_op` flag from front page
  - Recap sections contain Overhead and Profit line amounts
  - Line items may have individual O&P column values
**Warning signs:** `op_treatment_differs: true` but only one signal was checked.

### Pitfall 4: Depreciation Flags Are Front-Page Metadata, Not Per-Item
**What goes wrong:** Code assumes depreciation can be detected per line item. In Xactimate, depreciation settings are estimate-level parameters (front page metadata), not per-item flags.
**Why it happens:** Confusion between "Depreciate Material: Yes/No" (estimate-level setting) and actual depreciation amounts on individual items (only in ACV coverage tables).
**How to avoid:** Extract depreciation methodology from `case_metadata` (already parsed: `depreciate_material`, `depreciate_op`, `depreciate_non_material`, `depreciate_taxes`, `depreciate_removal`). Per-item depreciation amounts only appear in the trade summary / coverage table ACV columns.
**Warning signs:** Claiming per-item depreciation methodology when only estimate-level flags exist.

### Pitfall 5: Structured Outputs Pydantic Limitations
**What goes wrong:** Pydantic model with `default` values, `Optional` fields as bare `Optional[X]`, or `computed_field` properties fails with OpenAI Structured Outputs.
**Why it happens:** OpenAI Structured Outputs only supports a subset of JSON Schema. Key restrictions:
  - All fields must be `required` (no defaults allowed in the schema sent to API)
  - Optional fields must use `Union[X, None]` pattern, not bare `Optional[X]`
  - No `$ref` / recursive types
  - Max 500 enum values
  - No `minimum`/`maximum` numeric constraints
  - `additionalProperties: false` is required on all objects
**How to avoid:** Create separate "LLM response" Pydantic models distinct from internal pipeline models. LLM response models have all fields required with no defaults. Map from LLM response models to internal models after parsing.
**Warning signs:** `openai.BadRequestError` mentioning schema validation when calling `parse()`.

### Pitfall 6: Non-Deterministic Analysis (DATA-06 Violation)
**What goes wrong:** Same two PDFs produce different methodology analysis on different runs.
**Why it happens:** (a) Floating-point arithmetic order, (b) dict iteration order in older code, (c) fuzzy match tie-breaking.
**How to avoid:**
  - Use `round(x, 2)` for all money calculations (already done via `round2()`)
  - Sort all collections before processing
  - Use `score_cutoff` parameter in rapidfuzz to ensure deterministic tie-breaking
  - MethodologyAnalyzer must be pure function: same inputs always produce same outputs
**Warning signs:** Flaky tests that pass sometimes and fail other times.

## Code Examples

Verified patterns from official sources:

### OpenAI Structured Outputs with Pydantic (from OpenAI docs)
```python
# Source: https://developers.openai.com/api/docs/guides/structured-outputs/
from pydantic import BaseModel
from openai import OpenAI

client = OpenAI()

class Step(BaseModel):
    explanation: str
    output: str

class MathResponse(BaseModel):
    steps: list[Step]
    final_answer: str

completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful math tutor."},
        {"role": "user", "content": "solve 8x + 31 = 2"},
    ],
    response_format=MathResponse,
)

message = completion.choices[0].message
if message.parsed:
    result: MathResponse = message.parsed
    # result.steps and result.final_answer are typed
```

### RapidFuzz WRatio with extractOne (from RapidFuzz docs)
```python
# Source: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
from rapidfuzz import fuzz, process

# WRatio -- weighted ratio, best general-purpose scorer
score = fuzz.WRatio("Remove drywall - Loss area", "REMOVE DRYWALL LOSS AREA")
# Returns 0-100 float

# extractOne with score_cutoff for deterministic matching
match = process.extractOne(
    "Remove drywall",
    ["Remove drywall - water damage", "Install drywall", "Paint drywall"],
    scorer=fuzz.WRatio,
    score_cutoff=90.0,  # Only return if score >= 90
)
# Returns (matched_string, score, index) or None

# token_set_ratio -- good for subset matching (order-insensitive)
score = fuzz.token_set_ratio(
    "R&R Drywall 1/2 inch",
    "Drywall 1/2 inch - Remove & Replace"
)
# High score because tokens overlap despite different ordering
```

### Provenance Hash Generation
```python
# Using stdlib hashlib for deterministic claim IDs
import hashlib
import json

def provenance_id(source_estimate: str, source_field: str, raw_value: str) -> str:
    """Generate deterministic provenance hash for an analytical claim."""
    content = json.dumps({
        "source": source_estimate,
        "field": source_field,
        "value": raw_value,
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

### Xactimate Activity Code Extraction (from existing parser)
```python
# Already in parse/xactimate/constants.py:
# LINE_ITEM_PATTERN = r'^(\d+)\.\s+([A-Z]{3,})\s+([A-Z0-9<>+\-/]+)\s+(\S)\s+(.*)$'
# Groups: (line_num, CAT, SEL, ACT, description...)
#
# CAT = 3-letter category code (e.g., PNT, FCC, DRY, RFG)
# SEL = Selector code (e.g., DRYWALL, WTREXT)
# ACT = Activity character: + (Replace), - (Remove), R (Reset), & (Remove & Replace)
#
# Example parsed line item:
# "1. PNT DRYWALL + Drywall - prime + 2 coats  10.50 SF $1.25 $0.00 $13.13"
# => CAT="PNT", SEL="DRYWALL", ACT="+", desc="Drywall - prime + 2 coats"
```

### Depreciation Metadata Extraction (already in parser)
```python
# Already extracted by _parse_case_metadata() in parser.py:
# From front page of Xactimate PDF:
# "Price List: CALAW_FEB26  Depreciate Material: Yes  Depreciate O&P: No"
# "Depreciate Non-material: No  Depreciate Taxes: No"
# "Estimate: EST001  Depreciate Removal: No"
#
# Produces case_metadata dict:
# {
#     "price_list": "CALAW_FEB26",
#     "depreciate_material": True,
#     "depreciate_op": False,
#     "depreciate_non_material": False,
#     "depreciate_taxes": False,
#     "depreciate_removal": False,
#     "region": "California",
# }
```

## State of the Art (current year)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `client.chat.completions.create()` + `json.loads()` | `client.beta.chat.completions.parse(response_format=PydanticModel)` | OpenAI SDK 1.40+ (Aug 2024) | Eliminates JSON parse failures, guarantees schema compliance |
| FuzzyWuzzy for string matching | RapidFuzz (already using) | 2021+ | 20-100x faster, MIT license, maintained |
| Free-text LLM output with post-hoc validation | Structured Outputs with constrained decoding | Aug 2024 | Model is constrained at generation time, not just validated after |
| Manual JSON schema definition | Pydantic model auto-conversion to JSON schema | OpenAI SDK 1.40+ | SDK converts Pydantic to JSON schema automatically |

**New tools/patterns to consider:**
- `client.beta.chat.completions.parse()` -- the key migration target. Already supported by installed openai 1.108.0
- Pydantic v2 `model_dump_json()` / `model_validate_json()` for serialization -- already available in Pydantic 2.11.9

**Deprecated/outdated:**
- Manual `json.loads()` parsing of LLM output -- replaced by Structured Outputs
- `response_format={"type": "json_object"}` -- weaker guarantee, use Pydantic models instead
- fuzzywuzzy -- replaced by rapidfuzz (MIT license, faster)

## Open Questions

Things that could not be fully resolved:

1. **Mixed Estimate Formats**
   - What we know: System handles Xactimate Rough Draft (Layout B with CAT/SEL/ACT) and Final Draft (Layout A with DESCRIPTION/QUANTITY/UNIT/PRICE/TAX/RCV). Both are parsed.
   - What's unclear: When comparing a Rough Draft against a Final Draft, activity code matching is one-sided. How common is this in practice?
   - Recommendation: Support graceful fallback. If one estimate has activity codes and the other doesn't, skip activity code matching entirely and use description fuzzy matching for all items. Log a warning.

2. **Cumulated vs Non-Cumulated O&P**
   - What we know: Xactimate has a "Cumulate Overhead and Profit" setting where overhead is calculated first, then profit is calculated on (subtotal + overhead).
   - What's unclear: Whether this flag is visible in PDF output. The parser extracts O&P amounts but not the cumulation setting.
   - Recommendation: Detect cumulation by arithmetic: if `profit_total / (line_item_total + overhead_total) ~= profit_pct`, it's cumulated. Otherwise non-cumulated.

3. **Per-Line O&P Column Values**
   - What we know: Layout B (Rough Draft) has an "O&P" column per line item with values like checkmarks or amounts.
   - What's unclear: Exact encoding of per-line O&P in parsed output. The `HEADER_VARIANTS` map includes O&P column detection.
   - Recommendation: During implementation, examine actual parsed JSON for estimates with per-line O&P to confirm data availability.

4. **OpenAI Structured Outputs and `Optional` Fields**
   - What we know: Structured Outputs requires all fields be `required`. Optional fields must be expressed as `Union[type, None]`.
   - What's unclear: Whether the SDK's Pydantic integration handles this conversion automatically or requires manual schema adjustment.
   - Recommendation: Create dedicated "LLM response" Pydantic models with explicit `Union[X, None]` for nullable fields. Test with a simple model before migrating all passes.

## Sources

### Primary (HIGH confidence)
- **Codebase analysis** - Direct reading of `src/bid_comp/matchers.py`, `src/bid_comp/normalize.py`, `src/bid_comp/taxonomy.py`, `parse/xactimate/constants.py`, `parse/xactimate/parser.py`, `src/pipeline/state.py`, `src/pipeline/models.py`, `src/pipeline/orchestrator.py`, `src/llm/adapter.py`
- **OpenAI Structured Outputs docs** - https://developers.openai.com/api/docs/guides/structured-outputs/ -- parse() method, Pydantic integration, schema limitations
- **RapidFuzz docs** - https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html -- WRatio, token_set_ratio, process.extractOne
- **Xactimate category codes** - https://xactware.helpdocs.io/l/enUS/article/gb9lf49tdw-category-codes-in-xactimate-online -- full CAT code list
- **Xactimate O&P documentation** - https://xactware.helpdocs.io/l/enUS/article/k7j9gwcm98-add-o-p-in-the-new-xactimate-online -- O&P structure

### Secondary (MEDIUM confidence)
- **OpenAI Structured Outputs limitations** - https://community.openai.com/t/structured-outputs-deep-dive/930169 -- enum limits, optional field handling, additionalProperties requirements
- **Xactimate CAT/SEL review** - https://xactware.helpdocs.io/l/enUS/article/XZMAlfaqEg-cat-sel-review -- Activity code structure

### Tertiary (LOW confidence)
- **O&P cumulation behavior** - Inferred from Xactimate documentation descriptions, not verified against actual PDF output. Needs validation with real estimate data.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and in use. Versions verified.
- Architecture (MethodologyAnalyzer pattern): HIGH - Clean extension of existing PipelineState pattern. No new paradigms.
- Line-item matching: HIGH - Existing HeuristicMatcher works. Activity code extension is straightforward.
- O&P detection: MEDIUM - Parser extracts the data, but O&P structure variations in real PDFs need validation.
- Depreciation detection: HIGH - Parser already extracts all 5 depreciation flags from front-page metadata.
- OpenAI Structured Outputs migration: HIGH - SDK version 1.108.0 fully supports it. Pattern well-documented.
- Data provenance: HIGH - Pure Python pattern (hash + source tracking). No external dependencies.
- Scope alignment matrix: HIGH - Derived directly from line-item matching results. No new technology.

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain -- insurance estimating standards change slowly)
