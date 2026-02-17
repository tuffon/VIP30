# Stack Research: v2.0 Analytical Intelligence

**Domain:** Insurance estimate comparison analytics
**Researched:** 2026-02-17
**Confidence:** HIGH (core libraries verified via PyPI/official docs), MEDIUM (prompt patterns from training + search)

## Executive Summary

v2.0 adds analytical intelligence to an existing working system. The existing stack (FastAPI, OpenAI gpt-4o-mini, openpyxl, pandas, RQ workers) is solid and does not need replacing. The additions fall into four areas:

1. **Structured LLM output** -- Replace manual JSON parsing with Pydantic models + OpenAI Structured Outputs to guarantee schema compliance for analysis results, alert tags, and multi-mode narratives.
2. **Rules/emphasis engine** -- Pure Python rules engine using dataclasses and pandas, not a third-party rules framework. The domain is narrow enough (variance thresholds, percentile ranking, category-specific triggers) that a custom declarative approach beats external DSLs.
3. **Enhanced XLSX generation** -- openpyxl already supports everything needed: conditional formatting (CellIsRule, ColorScaleRule, DataBarRule, FormulaRule), NamedStyles, Table objects, and multi-sheet layouts. No new library needed.
4. **Neutral tone enforcement** -- Extend the existing 3-pass prompt pipeline with output-mode-specific system prompts, prohibited/required word lists per mode, and a tone validation gate. No new library needed.

**Primary recommendation:** Add `pydantic>=2.10` as the only new dependency. Everything else builds on existing openpyxl and OpenAI SDK capabilities.

## Recommended Stack (v2.0 Additions)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|---|---|---|---|
| Pydantic | >=2.10,<3 | Structured LLM output schemas, rule definitions, validation | OpenAI SDK has native Pydantic integration for Structured Outputs. Guarantees schema compliance at the API level -- no more manual JSON parsing/fixing. Already used implicitly via FastAPI; adding explicit models for LLM outputs is natural. |
| OpenAI Structured Outputs | (SDK feature, openai>=1.40) | Force LLM responses to match Pydantic schemas exactly | Eliminates the #1 fragility in the current pipeline: parsing free-form JSON from LLM responses. Pass a Pydantic model as `response_format` and get typed, validated output. Supported on gpt-4o-mini. |
| openpyxl conditional formatting | 3.1.5 (existing) | CellIsRule, ColorScaleRule, DataBarRule, FormulaRule for visual hierarchy | Already installed. The existing export_xlsx.py uses only Font, Alignment, and number_format. openpyxl 3.1.x has full conditional formatting support that is currently unused. |
| openpyxl Table + NamedStyle | 3.1.5 (existing) | Professional table banding, filter headers, reusable style templates | Table objects give automatic banding, filter arrows, and totals rows. NamedStyles avoid per-cell styling overhead on large sheets. |

### Supporting Libraries (Already Installed, New Usage)

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| pandas | >=2.0 (existing) | Variance percentile calculations, top-N ranking, statistical aggregation for rules engine | Computing "top 20% variance drivers", percentile ranks, category rollups. Already in requirements.txt. |
| openai | >=1.40 (existing, may need upgrade) | Structured Outputs via `response_format={"type": "json_schema", ...}` with Pydantic models | Every LLM call in the 3-pass pipeline. Current code uses raw httpx; migrating to the official SDK client unlocks Structured Outputs, automatic retries, and type safety. |

### No New Libraries Needed

The following capabilities are achievable with existing dependencies:

| Capability | How | Library |
|---|---|---|
| Rules engine | Python dataclasses + pandas operations | stdlib + pandas |
| Conditional formatting | openpyxl.formatting.rule module | openpyxl (existing) |
| Multi-sheet layouts | openpyxl Workbook.create_sheet() | openpyxl (existing) |
| Visual hierarchy (banding, headers) | openpyxl Table, NamedStyle, PatternFill | openpyxl (existing) |
| Tone validation | String matching + regex on LLM output | stdlib re module |
| Alert tag generation | Pydantic models + rules engine output | pydantic + stdlib |

## Detailed Implementation Guidance

### 1. Structured LLM Output with Pydantic

**Current state:** The adapter (`src/llm/adapter.py`) makes raw httpx calls and returns untyped strings. Callers parse JSON manually with `json.loads()` and hope the structure matches.

**v2.0 approach:** Define Pydantic models for every LLM output shape, then use OpenAI Structured Outputs to enforce them.

**Key models to define:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class CategoryAnalysis(BaseModel):
    category: str
    primary_total: float
    comparison_total: float
    delta: float
    delta_pct: float
    delta_drivers: list[str] = Field(description="WHY the numbers differ")
    line_item_evidence: list[str] = Field(description="Specific line items cited")
    severity: Literal["critical", "significant", "moderate", "minor"]
    alert_tags: list[str] = Field(description="Machine-readable flags like SCOPE_GAP, RATE_VARIANCE")

class AnalysisPassOutput(BaseModel):
    category_analyses: list[CategoryAnalysis]
    scope_gaps: list[str]
    overall_delta_direction: Literal["primary_higher", "comparison_higher", "similar"]
    confidence: Literal["high", "medium", "low"]
    methodology_notes: list[str] = Field(description="Differences in approach between estimates")

class DriverNarrative(BaseModel):
    category: str
    amounts: str
    narrative: str = Field(description="Three sentences: what differs, specifics, why")
    impact_rank: int = Field(description="1=highest impact")
    alert_tags: list[str]

class WriterPassOutput(BaseModel):
    overview: str
    key_drivers: list[DriverNarrative]
    scope_observations: list[str]
    suggested_followups: list[str]
    methodology_analysis: str = Field(description="How the two estimates approach the loss differently")
    output_mode: Literal["executive", "carrier", "litigation", "internal"]
```

**API integration pattern:**

```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    response_format=AnalysisPassOutput,
)
result: AnalysisPassOutput = completion.choices[0].message.parsed
```

**Important limitations of OpenAI Structured Outputs:**
- Does not support `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` constraints
- Does not support recursive schemas (`$ref` to self)
- All fields must be `required` (use `Optional` + explicit null handling instead of default values)
- Dictionary keys must be strings
- Keep models flat where possible; deeply nested models increase latency

**Confidence:** HIGH -- Verified via OpenAI official docs and PyPI. The `beta.chat.completions.parse()` method with Pydantic is the documented approach.

### 2. Rules/Emphasis Engine

**Current state:** No rules engine exists. The export code uses hardcoded thresholds (e.g., `abs_delta < 100` for "minor variance" in `_generate_fallback_narrative`).

**v2.0 approach:** Build a declarative rules engine using Python dataclasses and pandas. Do NOT use a third-party rules engine library.

**Why not a third-party rules engine:**
- `business-rules` (PyPI) -- Last release 2015, abandoned, Python 2 era
- `rule-engine` (PyPI) -- Adds a custom DSL/grammar; unnecessary complexity for <50 rules
- `durable-rules` -- Requires C compilation, Redis dependency in v1; overkill
- GoRules -- Rust-based, brings in FFI dependencies; wrong scale for this problem

**The domain is narrow:** ~20-50 rules operating on structured numeric data (deltas, percentages, counts). A declarative Python approach is simpler, testable, and debuggable.

**Recommended pattern:**

```python
from dataclasses import dataclass
from typing import Callable, Any
import pandas as pd

@dataclass
class EmphasisRule:
    id: str
    description: str
    condition: Callable[[pd.Series], bool]  # operates on a row
    severity: str  # "critical" | "significant" | "moderate" | "minor"
    alert_tag: str  # machine-readable tag
    message_template: str  # human-readable template

# Example rules
RULES = [
    EmphasisRule(
        id="TOP_20_VARIANCE",
        description="Category is in top 20% of variance drivers by absolute delta",
        condition=lambda row: row["delta_pct_rank"] >= 0.80,
        severity="critical",
        alert_tag="TOP_VARIANCE_DRIVER",
        message_template="{category} accounts for {delta_pct:.1%} of total variance",
    ),
    EmphasisRule(
        id="SCOPE_GAP_DETECTED",
        description="One estimate has zero for this category",
        condition=lambda row: row["primary_total"] == 0 or row["comparison_total"] == 0,
        severity="critical",
        alert_tag="SCOPE_GAP",
        message_template="{category} present in only one estimate",
    ),
    EmphasisRule(
        id="RATE_VARIANCE_HIGH",
        description="Unit rate differs by more than 30%",
        condition=lambda row: abs(row.get("rate_delta_pct", 0)) > 0.30,
        severity="significant",
        alert_tag="RATE_VARIANCE",
        message_template="{category} unit rates differ by {rate_delta_pct:.0%}",
    ),
]

def evaluate_rules(df: pd.DataFrame, rules: list[EmphasisRule]) -> pd.DataFrame:
    """Add alert_tags and severity columns based on rule evaluation."""
    df["alert_tags"] = [[] for _ in range(len(df))]
    df["severity"] = "minor"
    df["delta_pct_rank"] = df["delta"].abs().rank(pct=True)

    for rule in rules:
        mask = df.apply(rule.condition, axis=1)
        for idx in df[mask].index:
            df.at[idx, "alert_tags"].append(rule.alert_tag)
            # Severity escalation: keep highest
            if _severity_rank(rule.severity) > _severity_rank(df.at[idx, "severity"]):
                df.at[idx, "severity"] = rule.severity
    return df
```

**Confidence:** HIGH -- This is a standard Python pattern. No external verification needed; the implementation is pure stdlib + pandas.

### 3. Enhanced XLSX Generation

**Current state:** `export_xlsx.py` uses openpyxl with basic formatting: Font(bold), Alignment(wrap_text), number_format, merge_cells, and _autosize. Three sheets: Narrative Summary, Verisk Categories, Original Recap.

**v2.0 additions needed:**

#### A. Conditional Formatting (openpyxl built-in)

```python
from openpyxl.formatting.rule import (
    CellIsRule, ColorScaleRule, DataBarRule, FormulaRule, IconSetRule
)
from openpyxl.styles import PatternFill
from openpyxl.styles.differential import DifferentialStyle

# Red/green for positive/negative deltas
red_fill = PatternFill(bgColor="FFC7CE")
green_fill = PatternFill(bgColor="C6EFCE")

ws.conditional_formatting.add(
    "D2:D100",  # delta column
    CellIsRule(operator="greaterThan", formula=["0"],
               fill=green_fill)
)
ws.conditional_formatting.add(
    "D2:D100",
    CellIsRule(operator="lessThan", formula=["0"],
               fill=red_fill)
)

# Color scale for impact ranking (green=low impact, red=high impact)
ws.conditional_formatting.add(
    "E2:E100",
    ColorScaleRule(
        start_type="min", start_color="00AA00",
        end_type="max", end_color="AA0000"
    )
)

# Data bars for absolute variance magnitude
ws.conditional_formatting.add(
    "F2:F100",
    DataBarRule(start_type="min", end_type="max", color="638EC6")
)

# Formula-based: highlight rows where alert_tag contains SCOPE_GAP
ws.conditional_formatting.add(
    "A2:F100",
    FormulaRule(
        formula=['SEARCH("SCOPE_GAP",G2)>0'],
        fill=PatternFill(bgColor="FFFF00")
    )
)
```

#### B. NamedStyles for Visual Hierarchy

```python
from openpyxl.styles import NamedStyle, Font, PatternFill, Border, Side, Alignment

header_style = NamedStyle(name="header")
header_style.font = Font(bold=True, size=11, color="FFFFFF")
header_style.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
header_style.alignment = Alignment(horizontal="center", vertical="center")
header_style.border = Border(bottom=Side(style="thin"))
wb.add_named_style(header_style)

section_header_style = NamedStyle(name="section_header")
section_header_style.font = Font(bold=True, size=13, color="1F4E79")
wb.add_named_style(section_header_style)

alert_style = NamedStyle(name="alert_critical")
alert_style.font = Font(bold=True, color="CC0000")
alert_style.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
wb.add_named_style(alert_style)
```

#### C. Table Objects for Professional Layouts

```python
from openpyxl.worksheet.table import Table, TableStyleInfo

table = Table(displayName="ImpactRanking", ref="A1:F20")
table.tableStyleInfo = TableStyleInfo(
    name="TableStyleMedium2",
    showFirstColumn=False,
    showLastColumn=False,
    showRowStripes=True,
    showColumnStripes=False,
)
ws.add_table(table)
```

#### D. Multi-Sheet Layout for v2.0

| Sheet | Purpose | Key Formatting |
|---|---|---|
| Executive Snapshot | 1-page summary with totals, top 3 drivers, alert count | NamedStyles, merged header, DataBarRule on impact |
| Ranked Impact Table | All categories sorted by absolute delta, with alert tags | Table object with banding, ColorScaleRule, conditional fill |
| Scope Alignment Matrix | Side-by-side category presence/absence grid | Red/green PatternFill for gaps, Table object |
| Methodology Analysis | Text blocks comparing approaches | Merged cells, wrap_text, section headers |
| Narrative Summary | Enhanced version of current sheet with mode-specific content | Per-mode formatting (litigation=conservative, executive=bold) |
| Verisk Categories | Existing category matrix with added conditional formatting | CellIsRule on deltas, DataBarRule on amounts |
| Original Recap | Existing raw data | Freeze panes, Table object |

**Confidence:** HIGH -- All formatting features verified in openpyxl 3.1.x official documentation. Already using openpyxl 3.1.5.

### 4. Neutral/Defensible Tone Enforcement

**Current state:** The 3-pass pipeline (analysis_pass_v1 -> writer_pass_v1 -> compliance_rewrite_v1) already has substantial tone control:
- Prohibited words list in writer pass: "may", "might", "appears", "suggests", etc.
- Compliance rewrite pass removes hedge words and GPT-isms
- Three-sentence driver structure enforces factual pattern

**v2.0 additions for litigation mode:**

#### A. Output-Mode-Specific System Prompts

Define four prompt variants, each with mode-appropriate tone rules:

| Mode | Tone | Key Differences |
|---|---|---|
| Executive | Direct, summary-focused | Shorter overview, bullet-point drivers, no line-item evidence |
| Carrier | Technical, evidence-heavy | Full line-item citations, methodology analysis, scope gap detail |
| Litigation | Neutral, defensible, citation-heavy | NO judgment language, "observed" not "failed to include", all claims cite specific data, passive voice acceptable |
| Internal | Candid, action-oriented | Can include recommendations, "should investigate", "likely oversight" |

#### B. Litigation-Specific Prohibited/Required Terms

```python
LITIGATION_PROHIBITED = [
    # Judgment language
    "fails to include", "does not contemplate", "overlooked",
    "inadequate", "insufficient", "deficient", "lacking",
    "underestimation", "overestimation", "inflated", "deflated",
    # Speculative language
    "likely", "probably", "suggests", "indicates", "appears",
    "seems", "might", "may", "could", "possibly",
    # Advocacy language
    "should have included", "necessary work", "required scope",
    "full extent", "appropriate", "inappropriate",
]

LITIGATION_REQUIRED_PATTERNS = [
    # Every claim must reference data
    r"\$[\d,]+",  # Dollar amounts present
    # Use observation language
    "includes", "does not include", "contains", "omits",
    "lists", "does not list", "specifies", "does not specify",
]

LITIGATION_TONE_RULES = """
LITIGATION MODE - DEFENSIBLE NEUTRAL TONE:
1. OBSERVE, do not evaluate: "Estimate A includes X. Estimate B does not include X."
   NEVER: "Estimate A fails to include X" or "Estimate B properly includes X"
2. Every factual claim MUST cite a specific line item, quantity, or dollar amount
3. Use parallel structure: "Estimate A [verb] X at $Y. Estimate B [verb] Z at $W."
4. NO comparative adjectives: not "more comprehensive", "more thorough", "more complete"
5. NO causal language: not "because", "due to", "as a result of" -- just state both facts
6. Acceptable verbs: includes, lists, specifies, contains, omits, does not include, does not list
7. Acceptable framing: "The [amount] variance in [category] corresponds to [specific items]"
8. NEVER characterize an approach as better/worse/more appropriate
"""
```

#### C. Tone Validation Gate

```python
import re

def validate_litigation_tone(text: str) -> list[str]:
    """Return list of tone violations found in text."""
    violations = []
    for term in LITIGATION_PROHIBITED:
        if term.lower() in text.lower():
            violations.append(f"PROHIBITED_TERM: '{term}' found in output")

    # Check that dollar amounts are present (evidence requirement)
    sentences = text.split(".")
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 50 and not re.search(r"\$[\d,]+", sentence):
            # Long claim without dollar evidence
            if any(verb in sentence.lower() for verb in ["includes", "omits", "specifies"]):
                violations.append(f"UNSUPPORTED_CLAIM: '{sentence[:80]}...' lacks dollar citation")

    return violations
```

**Confidence:** MEDIUM -- The prohibited-term approach is proven (already working in v1.0.1 compliance pass). The litigation-specific framing rules are based on legal writing best practices from training data, not verified against a specific legal standard. Recommend review by a legal professional familiar with insurance litigation before production use.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| Pydantic models + OpenAI Structured Outputs | Manual JSON parsing (current approach) | Never for v2.0. Current approach is fragile. |
| Custom Python rules engine (dataclasses + pandas) | `rule-engine` PyPI package | If rules need to be user-editable via a DSL in the UI. Not needed for v2.0. |
| Custom Python rules engine | `business-rules` PyPI package | Never. Abandoned since 2015. |
| openpyxl conditional formatting | XlsxWriter library | If you need chart embedding. openpyxl handles all v2.0 requirements. |
| Mode-specific prompt templates (JSON files) | Pydantic-AI or LangChain for prompt management | If the system grows to 20+ LLM calls per pipeline. Current 3-5 pass pipeline is small enough for the existing TemplateRegistry. |
| OpenAI SDK `client.beta.chat.completions.parse()` | Current raw httpx calls | Never for v2.0. The SDK handles retries, rate limits, and Structured Outputs. |
| gpt-4o-mini with Structured Outputs | gpt-4o (full) | Only if output quality is insufficient for litigation mode. Test with gpt-4o-mini first -- it supports Structured Outputs and is 30x cheaper. |

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| LangChain | Massive dependency tree, abstraction overhead, version churn. VIP30's pipeline is 3-5 passes with clear data flow -- LangChain adds complexity without value at this scale. | Direct OpenAI SDK calls with Pydantic models |
| Pydantic-AI | New framework (pydantic-ai PyPI) that wraps LLM calls. Adds another abstraction layer over the OpenAI SDK. VIP30 already has a working adapter pattern. | Existing `OpenAIChatAdapter` upgraded to use SDK |
| XlsxWriter | Cannot read existing XLSX files (write-only). Would require replacing all openpyxl code. openpyxl does everything needed. | openpyxl (existing) |
| `business-rules` PyPI | Abandoned since 2015. No Python 3.10+ testing. | Custom dataclass-based rules |
| `durable-rules` PyPI | Requires C compilation and had Redis dependency. Overkill for <50 numeric threshold rules. | Custom dataclass-based rules |
| Jinja2 for prompt templates | Adds a dependency for something `str.format()` already handles. The existing PromptTemplate system works fine. | Existing `PromptTemplate` + `TemplateRegistry` |
| pandas Styler for XLSX formatting | pandas Styler exports to XLSX via openpyxl but with less control. Direct openpyxl gives full access to conditional formatting, tables, and named styles. | Direct openpyxl formatting |

## Migration Notes

### Current httpx -> OpenAI SDK

The current `OpenAIChatAdapter` makes raw httpx POST calls to `api.openai.com/v1/chat/completions`. This should be migrated to the official `openai` Python SDK to unlock Structured Outputs.

**Migration is incremental:**
1. The `openai` package is already in `requirements.txt` (>=1.12.0)
2. Upgrade to `openai>=1.40` for Structured Outputs support
3. Replace httpx calls with `client.beta.chat.completions.parse()` one template at a time
4. Each template gets a corresponding Pydantic output model
5. Existing templates continue to work during migration (SDK supports unstructured mode too)

**Key change in adapter:**
```python
# Before (current):
resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
content = resp.json()["choices"][0]["message"]["content"]
result = json.loads(content)  # fragile!

# After (v2.0):
from openai import OpenAI
client = OpenAI()
completion = client.beta.chat.completions.parse(
    model=self.model,
    messages=messages,
    response_format=output_model,  # Pydantic class
)
result = completion.choices[0].message.parsed  # typed Pydantic instance
```

### Prompt Template Evolution

Current templates define JSON structure in prose within the user prompt. With Structured Outputs, the JSON schema is enforced by the API. System prompts focus purely on tone/content rules, user prompts focus on input data.

**Template split for v2.0:**
- `analysis_pass_v2.json` -- System prompt for analysis, NO JSON schema in prose
- `writer_pass_v2_executive.json` -- Executive mode tone rules
- `writer_pass_v2_carrier.json` -- Carrier mode tone rules
- `writer_pass_v2_litigation.json` -- Litigation mode tone rules (strictest)
- `writer_pass_v2_internal.json` -- Internal mode tone rules (most permissive)
- `compliance_rewrite_v2.json` -- Mode-aware compliance with tone validation results injected

## Installation

Only one new dependency:

```bash
pip install "pydantic>=2.10,<3"
pip install --upgrade "openai>=1.40"
```

Note: Pydantic is already installed transitively via FastAPI. Adding it explicitly pins a minimum version that guarantees Structured Outputs compatibility.

## Sources

### Primary (HIGH confidence)
- [OpenAI Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs/) -- Pydantic integration, `response_format` API, model compatibility
- [openpyxl 3.1.x conditional formatting docs](https://openpyxl.readthedocs.io/en/stable/formatting.html) -- CellIsRule, ColorScaleRule, DataBarRule, FormulaRule, IconSetRule
- [openpyxl 3.1.x styles docs](https://openpyxl.readthedocs.io/en/stable/styles.html) -- NamedStyle, PatternFill, Table objects
- [openpyxl PyPI](https://pypi.org/project/openpyxl/) -- Version 3.1.5 confirmed current (Nov 2025)
- [Pydantic PyPI](https://pypi.org/project/pydantic/) -- Version 2.12.5 confirmed current
- [OpenAI Python SDK PyPI](https://pypi.org/project/openai/) -- Version 2.x confirmed current (Feb 2026)
- [Pydantic + OpenAI integration guide](https://pydantic.dev/articles/llm-intro) -- Schema limitations, best practices

### Secondary (MEDIUM confidence)
- [OpenAI Structured Outputs limitations](https://medium.com/@aviadr1/how-to-fix-openai-structured-outputs-breaking-your-pydantic-models-bdcd896d43bd) -- Schema subset limitations verified against official docs
- [Python rule engine landscape survey](https://www.nected.ai/blog/python-rule-engines-automate-and-enforce-with-python) -- Confirmed business-rules, rule-engine, durable-rules as main options; all unsuitable for this use case

### Tertiary (LOW confidence)
- Litigation tone patterns -- Based on training data knowledge of legal writing conventions and insurance claims documentation. Not verified against a specific legal standard. Recommend professional legal review before production use of litigation mode output.

## Metadata

**Confidence breakdown:**
- Pydantic + Structured Outputs: HIGH -- Official OpenAI + Pydantic docs, PyPI versions verified
- Rules engine approach: HIGH -- Pure Python pattern, no external dependency risk
- openpyxl formatting: HIGH -- Official docs, already using the library
- Litigation tone patterns: MEDIUM -- Proven prohibited-term approach (v1.0.1), but litigation-specific framing rules need legal review
- OpenAI SDK version: MEDIUM -- PyPI confirms 2.x line exists but exact latest minor version may differ

**Research date:** 2026-02-17
**Valid until:** 2026-04-17 (60 days -- all core libraries are stable/mature)
