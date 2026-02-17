# Pitfalls Research

**Domain:** Insurance estimate comparison analytics
**Researched:** 2026-02-17
**Confidence:** HIGH (domain + codebase analysis), MEDIUM (LLM-specific patterns from community reports)

---

## Critical Pitfalls

### P-01: Hedge Language Leaking into Litigation-Ready Output

**What goes wrong:** LLM-generated narratives default to epistemic hedging ("appears to," "may indicate," "suggests that," "likely due to") which is standard academic writing but fatal in insurance litigation contexts. When an adjuster's report says "the variance appears to suggest a scope difference," opposing counsel reads it as the tool itself expressing doubt about its own findings. A fact becomes a conjecture. The report's evidentiary weight drops to zero.

**Why it happens:** GPT-4o-mini's training distribution is overwhelmingly academic/journalistic, where hedging signals intellectual honesty. The model has no concept that in insurance estimate comparison, the numbers ARE the facts -- there is nothing uncertain about "$4,200 delta in Flooring." The hedge is not epistemic humility; it is a factual error about certainty.

**Current exposure:** VIP30 already has GATE-01 (HedgingChecker) and GATE-05 (AnalystToneChecker) catching 13 hedge words and 10 analyst phrases. However, the current list has gaps:

- Missing insurance-specific hedges: "in our opinion," "it would appear," "one could argue," "it is reasonable to assume," "this may be due to"
- Missing pseudo-neutral hedges that LLMs favor: "it is worth considering," "this warrants further review" (when the data already answers the question)
- Missing comparative hedges: "relatively higher," "somewhat lower" (vague when exact numbers exist)

**Warning signs:**
- Compliance pass triggering on >30% of jobs (means writer prompt is not preventing hedges)
- Narratives using qualitative language where quantitative language exists ("significantly higher" instead of "$4,200 higher, representing 34% of total variance")
- Any narrative containing "may," "might," "could," "appears" when describing computed deltas

**How to avoid:**
1. Expand GATE-01 hedge word list with insurance-litigation-specific terms (see list above)
2. Add a new quality gate: GATE-07 "Quantification Check" -- every narrative sentence referencing a delta MUST contain the dollar amount and percentage. No exceptions.
3. In the writer prompt, add an explicit instruction: "The numbers in the data are facts, not estimates. Do not hedge factual numerical differences. Say 'Flooring is $4,200 higher in Estimate B' not 'Flooring appears to be higher.'"
4. Add a banned-phrases list to the writer prompt itself (not just post-hoc checking): "NEVER use: appears to, suggests that, may indicate, likely due to, it would seem, one could argue"

**Phase to address:** Narrative Quality (priority 3). Must be in place before any output mode ships.

---

### P-02: Emphasis Logic Creating False Hierarchy (The "Everything Is Important" Trap)

**What goes wrong:** Rules engines flag too many items as important, which makes nothing important. If a report highlights 12 out of 15 categories as "significant variance," the adjuster learns to ignore highlights. Worse: if emphasis thresholds are set too low, normal variance noise gets flagged as signal, creating false urgency that undermines trust in actual critical findings.

**Why it happens:** Developers set thresholds based on absolute dollar amounts ($500 difference = flagged) without accounting for relative context. A $500 delta in a $200,000 estimate is noise. A $500 delta in a $2,000 line item is a 25% variance and genuinely significant. Additionally, using fixed thresholds fails across different claim sizes -- a $50K residential claim and a $500K commercial claim need different sensitivity.

**Specific anti-patterns:**
- **Flat dollar thresholds:** "$1,000 difference = flag" ignores claim context
- **Too many flag types:** More than 3-4 visual flag levels (critical/high/medium/low/info) creates a rainbow spreadsheet nobody reads
- **Flagging known patterns as anomalies:** O&P differences between carrier and contractor estimates are EXPECTED, not anomalous. Flagging them like errors confuses adjusters who know this.
- **Alert without action:** "Large variance detected" without "Verify line item quantities in Roofing section" is useless

**Warning signs:**
- More than 30% of categories flagged as "significant" in an average report
- Users ignoring flags (measurable if you track which flagged items users click/expand)
- Flags without associated recommended actions
- Same flag level applied to $200 and $20,000 variances

**How to avoid:**
1. Use percentage-of-total-variance as primary ranking, not absolute dollars. The "top 20% drivers" approach in the requirements is correct -- enforce it strictly.
2. Cap emphasis at top 3-5 items per report. If everything is flagged, nothing is.
3. Use exactly 3 severity tiers: Critical (structural/methodology difference), Notable (top variance drivers), and Informational (everything else). No more.
4. Require every flag to have an associated action recommendation: "Review [specific thing] for [specific reason]"
5. Make O&P and depreciation methodology differences a SEPARATE section, not mixed into variance flags. These are structural observations, not anomalies.

**Phase to address:** Intelligence Layer (priority 2). Get this right before Visual Hierarchy (priority 4) renders it.

---

### P-03: Subjective Characterization Disguised as Analysis

**What goes wrong:** The output uses evaluative adjectives that embed opinion into what should be factual comparison. Words like "excessive," "inadequate," "reasonable," "appropriate," "inflated," "undervalued" are judgments, not observations. In litigation, opposing counsel will ask: "Who determined this was 'excessive'? Your software? Based on what standard?"

**Why it happens:** LLMs naturally produce evaluative language because their training data is full of it. Insurance adjusters themselves use evaluative language in informal communication. The temptation is to make the tool "sound like an adjuster." But there is a critical difference: an adjuster can defend their judgment in deposition. Software cannot.

**Specific dangerous words/phrases:**
- **Judgment words:** excessive, inadequate, inflated, unreasonable, appropriate, fair, proper, sufficient, deficient, overestimated, underestimated
- **Causal attribution:** "caused by," "due to" (implies root cause knowledge the tool does not have -- it can observe correlation, not causation)
- **Conclusory phrases:** "This confirms," "This proves," "This demonstrates" (the data shows a difference; drawing conclusions is the adjuster's job)
- **Comparative value judgments:** "better estimate," "more accurate," "more thorough" (the tool compares; it does not judge quality)

**Warning signs:**
- Any narrative containing words from the dangerous list above
- Narrative drawing causal conclusions ("The higher cost is due to the contractor padding the estimate")
- Tool output being quoted in depositions as evidence of bias
- Output that could only be correct from one party's perspective

**How to avoid:**
1. Add GATE-08 "Judgment Language Check" scanning for evaluative adjectives and conclusory phrases
2. Enforce observational framing in the writer prompt: "You are describing WHAT differs, not WHY or WHETHER it should. Never characterize a difference as good, bad, right, or wrong."
3. Use the pattern: "[Quantity] differs by [amount] ([percentage]). [Estimate A] includes [X]; [Estimate B] does not." -- pure observation.
4. Replace causal language with observational: "The $4,200 difference in Flooring correlates with 3 additional line items present in Estimate B" (NOT "is caused by")
5. Test every output mode's language through a "deposition filter": could every sentence survive "How did your software determine that?"

**Phase to address:** Narrative Quality (priority 3). Non-negotiable for Litigation mode (priority 5).

---

### P-04: LLM Fabricating Line Item Evidence

**What goes wrong:** When prompted to explain a delta, the LLM invents specific line items, quantities, or unit costs that do not exist in the input data. It might say "The delta is driven by 3 additional window units at $450 each" when the actual data shows no window-level granularity. This is catastrophic in a legal context -- fabricated evidence in a report used for carrier negotiation or litigation.

**Why it happens:** GPT-4o-mini is trained to produce plausible-sounding explanations. When the input data provides only category-level totals (e.g., "Flooring: $12,500 vs $8,300") without line-item detail, the model confabulates specific line items to make the narrative sound authoritative. The current pipeline's `line_item_evidence` field in `CategoryAnalysis` may receive fabricated data from the analysis pass.

**Current exposure:** The v1.0.1 pipeline's analysis pass extracts `delta_drivers` and `line_item_evidence` from LLM output. If the input PDF parsing does not provide line-item granularity for a given category, the LLM fills in plausible but fake specifics. The writer pass then uses these fabricated specifics as if they were ground truth.

**Warning signs:**
- `line_item_evidence` contains specific quantities or unit costs not present in the parsed PDF data
- Narrative mentions specific product names, model numbers, or brand names not in source data
- Evidence cites "3 additional line items" when the parser only extracted category totals
- Any specificity in narrative that exceeds the specificity of the input data

**How to avoid:**
1. Implement a data provenance check: every claim in `line_item_evidence` must trace back to parsed data. If the parser extracted only category totals, the narrative MUST say "Category-level comparison only; line-item detail not available."
2. Add a new quality gate: GATE-09 "Evidence Grounding Check" -- compare narrative claims against actual parsed data fields. Flag any specificity that exceeds input granularity.
3. In the analysis prompt, explicitly instruct: "Only cite line items that appear verbatim in the input data. If you only have category totals, say so. NEVER invent specific line items, quantities, or unit costs."
4. Structure the data contract so the writer pass KNOWS what level of granularity is available (category-only vs. line-item) and adjusts language accordingly.
5. Add a `data_granularity` field to `CategoryAnalysis`: "category_total_only" | "line_item_available" | "partial_line_items"

**Phase to address:** Methodology & Data Foundation (priority 1). Must be solved at the data layer before intelligence or narrative layers build on it.

---

### P-05: Rules Engine Rigidity Across Claim Types

**What goes wrong:** A rules engine tuned for residential water damage claims ($20K-$80K) produces nonsensical output on commercial fire claims ($500K+) or small supplemental claims ($2K-$5K). Fixed thresholds, fixed category expectations, and fixed flag logic break when claim profiles vary.

**Why it happens:** Rules are authored against the most common case seen during development. Edge cases and different claim profiles are not tested. The system has no awareness of claim type, size, or context -- it applies the same rules universally.

**Specific failure modes:**
- **Small claims:** A $200 variance that is 40% of a $500 category total gets ignored because it is below the absolute dollar threshold, but it is the most significant finding
- **Large commercial claims:** Every category exceeds absolute thresholds, so everything is flagged, making the report useless
- **Supplement claims:** Comparing an original estimate to a supplement should only flag NEW or CHANGED items, not recalculate everything
- **Different estimate structures:** Carrier estimates may group categories differently than contractor estimates, causing false "missing category" flags

**Warning signs:**
- Reports for very small or very large claims have dramatically different flag counts than typical claims
- "Missing category" flags that are actually category naming differences (e.g., "HVAC" vs "HVAC / Mechanical" vs "Heating & Cooling")
- Rules that make sense for one claim size producing absurd results at another

**How to avoid:**
1. Use percentage-based thresholds as primary, with absolute-dollar minimums as floor (e.g., flag if >15% variance AND >$500)
2. Implement claim-size normalization: divide the claim into tiers (small/medium/large) and adjust emphasis sensitivity per tier
3. Build category name normalization into the methodology layer (mapping "HVAC" to "HVAC / Mechanical" etc.) before rules fire
4. Do NOT attempt to detect claim type automatically in v2.0 -- instead, make threshold parameters configurable and document defaults clearly
5. Test rules against at least 3 claim size profiles: small residential (<$20K), typical residential ($20K-$100K), large/commercial (>$100K)

**Phase to address:** Intelligence Layer (priority 2), validated in Methodology & Data Foundation (priority 1) for category normalization.

---

### P-06: LLM Prompt Producing Inconsistent JSON Structure

**What goes wrong:** The LLM returns JSON with missing fields, unexpected field names, wrong types (string instead of number), or structurally valid but semantically wrong content. The current codebase already handles this partially (JSON repair in `_repair_json`, fallback narratives), but each new output mode and enhanced data contract multiplies the surface area for structural failures.

**Why it happens:** GPT-4o-mini's structured output compliance is imperfect even with json_schema response_format. Community reports document missing keys, fabricated enum values, and intermittent schema violations. The more complex the output schema, the higher the failure rate. Adding methodology analysis blocks, alert tags, multiple output modes, and enhanced evidence structures dramatically increases schema complexity.

**Current exposure:** The existing `_repair_json` handles trailing commas and missing commas. The `_parse_writer_response` has extensive fallback logic. But v2.0 schemas will be significantly more complex (methodology analysis, alert tags, evidence grounding, output mode variants).

**Warning signs:**
- Compliance pass JSON parse failure rate >5%
- New fields consistently returning null/empty despite data being available in the prompt
- Schema repair logic growing to handle more than 3-4 patterns
- Different output for the same input on repeated calls (structural instability)

**How to avoid:**
1. Use OpenAI's native structured output (response_format with json_schema) instead of prompt-only JSON instructions. This uses constrained decoding and has near-100% structural compliance.
2. If using prompt-based JSON, keep schemas flat and simple. Avoid deeply nested structures. Split complex outputs into multiple LLM calls with simpler schemas each.
3. Define Pydantic models for every LLM output contract and validate immediately after parsing. Reject and retry (with backoff) rather than accepting malformed data.
4. Add a `schema_version` field to every LLM output to detect when the model is producing output for a different schema than expected.
5. For v2.0's increased complexity: split the analysis pass into sub-passes (methodology extraction, category analysis, evidence grounding) rather than one monolithic prompt that returns everything.

**Phase to address:** Methodology & Data Foundation (priority 1) for the data contracts; each subsequent phase for its own LLM interactions.

---

### P-07: XLSX Report Information Overload

**What goes wrong:** The enhanced XLSX becomes a data dump that adjusters cannot navigate. Too many sheets, too many columns, inconsistent formatting, conditional formatting that creates a "Christmas tree" effect where every cell has a different color, and narrative text crammed into narrow cells that require horizontal scrolling.

**Why it happens:** Each feature (methodology analysis, alert tags, scope matrix, ranked impact table, executive snapshot) gets its own section or sheet, and nobody designs the holistic reading experience. Developers add data because they can, not because it serves the user's workflow.

**Specific XLSX anti-patterns in the current codebase and v2.0 plans:**
- **Current:** Narrative text in column E of the Key Cost Drivers table is cut off at column width 80 (the `_autosize` max). Long narratives are unreadable.
- **Current:** The "Original Recap" sheet is raw data with no summarization -- useful for audit but confusing as a third sheet when users expect the report to be the first two sheets.
- **Planned risk:** Adding conditional formatting for every flag type across every cell will make the sheet look like a heatmap rather than a professional report.
- **Planned risk:** Multi-sheet structure without a clear navigation pattern (e.g., no table of contents, no hyperlinks between sheets) means users open the file and do not know where to start.

**Warning signs:**
- More than 5 sheets in a single workbook (adjusters will not navigate past 3-4)
- Conditional formatting using more than 3 colors (green/yellow/red or blue/white/red)
- Any cell requiring horizontal scroll to read
- Users printing the report and finding it unreadable

**How to avoid:**
1. Design for print first: every sheet should look professional when printed on letter-size paper in landscape orientation
2. Maximum 4-5 sheets: Executive Summary, Ranked Impact (the workhorse), Methodology Comparison, Category Detail, Raw Data (hidden by default)
3. Conditional formatting limited to 3 colors maximum, applied only to the delta/variance columns, never to narrative text cells
4. Narrative cells: set column width to 60-80 characters, enable wrap_text, and set row height to accommodate 2-3 lines minimum
5. Sheet 1 (Executive Summary) should be self-contained: an adjuster should be able to make a decision from sheet 1 alone, then drill into subsequent sheets only if needed
6. Add freeze panes on every data sheet (already done for some, but enforce universally)

**Phase to address:** Visual Hierarchy (priority 4). Design the sheet structure and formatting system before populating with v2.0 data.

---

### P-08: Output Modes as Template Proliferation Instead of Content Filtering

**What goes wrong:** Each output mode (Executive, Carrier Negotiation, Litigation, Internal Estimator) becomes a separate code path with its own prompt, its own template, its own formatting, and its own bugs. Maintenance cost quadruples. Bugs fixed in one mode are not fixed in others. Tone calibration in the writer prompt diverges across modes.

**Why it happens:** The intuitive approach is "Litigation mode needs different language, so give it a different prompt." This leads to 4 writer prompts, 4 compliance templates, 4 XLSX formatters, and 4 sets of quality gates. Changes to base logic must be replicated 4 times.

**The STATE.md already identifies the correct approach:** "Output modes as content filtering, not separate templates." This decision must be enforced rigorously.

**Warning signs:**
- More than 1 writer prompt template (there should be one base template with mode-specific parameters)
- Quality gates that differ between modes (there should be one gate set, with mode-specific threshold overrides)
- XLSX export functions that branch on mode early (mode should affect what data is included and how it is formatted, not the generation logic)
- Any copy-paste between mode-specific code paths

**How to avoid:**
1. Single analysis pass, single writer pass, single compliance pass. Mode affects: (a) which sections are included, (b) tone parameters passed to the writer, (c) which XLSX sheets are generated, (d) verbosity of narratives.
2. Implement mode as a configuration object, not branching logic:
   ```python
   class OutputMode:
       include_methodology: bool
       include_line_items: bool
       max_narrative_sentences: int
       tone: Literal["neutral_litigation", "direct_negotiation", "executive_summary", "diagnostic_detail"]
       xlsx_sheets: List[str]
       quality_overrides: Dict[str, int]  # e.g., {"max_hedges": 0} for litigation
   ```
3. Litigation mode is the BASE tone -- the most restrictive. Other modes RELAX from litigation, not the reverse. This ensures all modes are litigation-safe by default.
4. Test: every narrative generated in Executive mode should also pass Litigation mode quality gates (with possibly stricter thresholds in Litigation mode for hedging).

**Phase to address:** Output Modes (priority 5), but the architecture decision must be made in Narrative Quality (priority 3) to prevent wrong patterns from forming.

---

### P-09: Methodology Section Becoming Opinion Instead of Observation

**What goes wrong:** The methodology analysis block (O&P inclusion, depreciation, unit pricing source, locality factors) starts describing what IS different between two estimates but drifts into implying what SHOULD be different or which approach is "correct." For example: "Estimate A uses ACV depreciation while Estimate B uses RCV. The RCV approach provides a more complete representation of repair costs." The second sentence is an opinion that takes a side.

**Why it happens:** Methodology comparison inherently invites evaluation. The LLM's training data is full of articles explaining why one depreciation method is "better." The prompt must aggressively prevent this.

**Warning signs:**
- Methodology section using comparative adjectives ("more complete," "more thorough," "more conservative")
- Any sentence in methodology that could be read as favoring one estimate over the other
- Methodology observations that include industry standards as implicit judgment ("Standard practice is RCV" implies the ACV estimate is substandard)

**How to avoid:**
1. Methodology section should ONLY use the pattern: "[Estimate A] uses [approach X]. [Estimate B] uses [approach Y]. The difference in approach accounts for approximately $[Z] of the total variance."
2. NEVER reference industry standards, "best practices," or "common approaches" in methodology comparison -- these are opinion proxies
3. Add GATE-10 "Methodology Neutrality Check" scanning methodology text for comparative adjectives and standard-referencing phrases
4. Frame methodology differences as structural observations that EXPLAIN variance, not as deficiencies to correct
5. If the system detects O&P is missing in one estimate, the flag should say "O&P line items not present in Estimate A" -- NOT "Estimate A is missing O&P" (which implies it should be there)

**Phase to address:** Methodology & Data Foundation (priority 1) for the data model; Narrative Quality (priority 3) for the language enforcement.

---

### P-10: Executive Summary Compressing Nuance into Misleading Simplicity

**What goes wrong:** The executive snapshot reduces a complex comparison to "Total Delta: $12,400" and "Top 3 Drivers: Roofing, Flooring, HVAC" without context. An adjuster reads this and forms a conclusion before seeing that the Roofing delta is a methodology difference (O&P treatment) while the Flooring delta is a genuine scope gap. Compressing these fundamentally different types of variance into the same "top 3" list misleads.

**Why it happens:** Executive summaries are designed for speed. But speed without classification creates false equivalence. A $5,000 delta from missing scope is NOT the same as a $5,000 delta from different O&P treatment, even though they are the same dollar amount.

**Warning signs:**
- Executive summary listing deltas by magnitude only, without categorizing the TYPE of difference
- Users making decisions from the summary without opening detail sheets
- Summary that could apply to completely different underlying data (too generic)

**How to avoid:**
1. Executive summary must classify each top driver: "Scope Difference," "Methodology Difference," "Pricing Variance," or "Quantity Variance"
2. Use the pattern: "Total delta: $12,400. Scope differences account for $7,200 (58%). Methodology differences account for $4,100 (33%). Pricing variance accounts for $1,100 (9%)."
3. Never list raw deltas without classification context
4. Include a one-line structural observation: "Estimates differ in O&P treatment and depreciation methodology, accounting for X% of total variance independent of scope differences."
5. Test: show the executive summary alone to someone unfamiliar with the claim. If they form a misleading conclusion, the summary needs more context.

**Phase to address:** Visual Hierarchy (priority 4), informed by Methodology & Data Foundation (priority 1) classification logic.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|------------------|----------------|-----------------|
| Hardcoded thresholds ($1000, 15%, etc.) | Quick rules engine MVP | Every claim type needs different thresholds; adjusters request customization | v2.0 MVP only; must become configurable by v2.1 |
| Single writer prompt for all modes | Faster initial development | Mode-specific tone drift, copy-paste bugs when modes diverge | Never -- design the mode-as-config pattern from day one |
| Skipping evidence grounding validation | Faster narrative generation | Fabricated line items in litigation reports | Never -- this is a legal liability |
| Inline quality gate thresholds | Quick iteration during development | Thresholds scattered across code, hard to tune as a system | v2.0 development only; consolidate to config before release |
| Prompt-based JSON instead of structured output API | Works with current LLM adapter | Higher parse failure rate, more repair code, more fallback paths | Acceptable temporarily if LLM adapter does not support response_format |
| Monolithic analysis prompt (methodology + categories + evidence in one call) | Fewer LLM calls, lower latency | Longer prompts hit context limits, lower quality per-section, harder to cache | Acceptable for v2.0 if prompts stay under 4K tokens; split in v2.1 |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Quality gate spiral: compliance rewrite triggers new violations | Rewrite count >2 per job, oscillating quality scores | Cap rewrites at 1; if still failing after 1 rewrite, use deterministic fallback narrative | Large complex reports with many categories |
| Rules engine evaluating all categories against all rules | Latency spike proportional to categories x rules | Short-circuit: only evaluate rules on top-N categories by delta; skip categories below noise floor | Claims with 30+ categories (commercial) |
| XLSX generation for large reports | Memory spike, timeout on worker | Stream writes with openpyxl write-only mode for data sheets; keep narrative sheet in normal mode | Reports with >500 line items |
| LLM context window overflow with detailed evidence | Truncated input causing hallucinated output | Compute token estimate before LLM call; if exceeding 80% of context window, summarize input data first | Large commercial estimates with 100+ line items per category |
| Conditional formatting applied cell-by-cell | XLSX file size bloats, slow to open | Use openpyxl conditional formatting rules (applied to ranges, not individual cells) | Reports with >200 data rows |

---

## "Looks Done But Isn't" Checklist

- [ ] **Hedge-free narratives pass quality gates but still contain subtle judgment:** Quality gates catch "appears to" but miss "the more detailed estimate" (comparative judgment). Manual review sample of 20 reports needed before shipping each output mode.
- [ ] **Rules engine works on test data but not on real Xactimate PDFs:** Xactimate category names vary by version, region, and estimator preferences. Test against 10+ real PDF pairs, not synthetic data.
- [ ] **Executive summary generated but not self-contained:** The summary references categories or findings that only make sense if you read the detail sheets. Test: can someone act on the summary alone?
- [ ] **Methodology comparison implemented but not classified:** The system detects O&P differences but does not TAG them as "methodology" versus "scope" versus "pricing." Classification is the hard part, not detection.
- [ ] **Output modes switch content but share the wrong defaults:** Litigation mode accidentally inherits Executive mode's relaxed hedge thresholds because the config inheritance is wrong.
- [ ] **Conditional formatting renders correctly in openpyxl but looks wrong in Excel/Google Sheets:** Test XLSX output in: Excel Desktop, Excel Online, Google Sheets, LibreOffice. Conditional formatting rendering differs across platforms.
- [ ] **Alert tags generated but not actionable:** Flags say "Large variance in Other" but do not say what to do about it. Every flag needs a recommended next step.
- [ ] **Evidence grounding works for the writer pass but not for the methodology pass:** Each LLM pass that can reference specific data needs its own grounding validation, not just the writer.
- [ ] **Tone is neutral in the narrative but biased in the XLSX section headers:** Section titles like "Estimate Deficiencies" or "Missing Items" imply fault. Use "Scope Differences" and "Items Present in One Estimate Only."
- [ ] **Print layout breaks with conditional formatting:** Colors that look distinct on screen become indistinguishable when printed in grayscale. Use patterns or bold in addition to color.

---

## Pitfall-to-Phase Mapping

| Pitfall | ID | Prevention Phase | Verification |
|---------|----|-----------------|--------------|
| Hedge language in output | P-01 | Narrative Quality (P3) | Expanded quality gate word list; 0 hedge words in litigation mode output; sample 20 reports |
| Everything-is-important emphasis | P-02 | Intelligence Layer (P2) | Flagged items per report <= 5; percentage-based thresholds; 3-tier severity only |
| Subjective characterization | P-03 | Narrative Quality (P3) | Judgment language gate; deposition filter test on all output modes |
| Fabricated line item evidence | P-04 | Methodology & Data (P1) | Data provenance check; granularity field on CategoryAnalysis; zero fabricated evidence in sample |
| Rules engine rigidity across claim sizes | P-05 | Intelligence Layer (P2) | Test against 3 claim size tiers; percentage+floor thresholds; category name normalization |
| Inconsistent LLM JSON structure | P-06 | Methodology & Data (P1) | Use structured output API; Pydantic validation on all LLM responses; parse failure rate <2% |
| XLSX information overload | P-07 | Visual Hierarchy (P4) | Max 5 sheets; max 3 colors; print test; platform compatibility test |
| Output mode template proliferation | P-08 | Output Modes (P5), architected in P3 | Single writer prompt; mode-as-config object; all modes pass litigation quality gates |
| Methodology opinion vs observation | P-09 | Methodology & Data (P1) + Narrative Quality (P3) | Methodology neutrality gate; no comparative adjectives; pattern-based framing |
| Executive summary false simplicity | P-10 | Visual Hierarchy (P4), informed by P1 | Variance classification in summary; methodology vs scope breakdown; standalone comprehension test |

---

## Sources

### Primary (HIGH confidence)
- VIP30 codebase analysis: `pipeline/quality.py` (quality gates), `pipeline/passes/writer.py` (writer pass), `pipeline/passes/compliance.py` (compliance pass), `pipeline/models.py` (data contracts), `bid_comp/export_xlsx.py` (XLSX generation)
- VIP30 `.planning/PROJECT.md` and `.planning/STATE.md` (v2.0 requirements and architecture decisions)

### Secondary (MEDIUM confidence)
- [OpenAI Structured Outputs documentation](https://platform.openai.com/docs/guides/structured-outputs) - JSON schema compliance capabilities and limitations
- [OpenAI community: Structured Outputs not reliable with GPT-4o-mini](https://community.openai.com/t/structured-outputs-not-reliable-with-gpt-4o-mini-and-gpt-4o/918735) - documented field-level reliability issues
- [IBM: What Is Alert Fatigue](https://www.ibm.com/think/topics/alert-fatigue) - alert fatigue patterns and prevention
- [Datadog: Best Practices to Prevent Alert Fatigue](https://www.datadoghq.com/blog/best-practices-to-prevent-alert-fatigue/) - threshold tuning and severity tiering
- [United Policyholders: Guidelines for Reviewing Adjusters' and Contractors' Estimates](https://uphelp.org/claim-guidance-publications/guidelines-for-reviewing-adjusters-and-contractors-estimates/) - estimate comparison standards
- [United Policyholders: Xactimate Demystified](https://uphelp.org/claim-guidance-publications/xactimate-demystified/) - Xactimate structure and comparison patterns
- [Property Insurance Coverage Law Blog: Insurance Company Engineering Report Bias](https://www.propertyinsurancecoveragelaw.com/blog/insurance-company-engineering-report-bias/) - report language bias in insurance context
- [Vena: Excel Formatting Tips for Finance](https://www.venasolutions.com/blog/how-to-format-your-excel-spreadsheet-10-tips) - professional spreadsheet design
- [SOA: Excel Should Not Be Your Production Actuarial System](https://www.soa.org/sections/small-insurance/small-insurance-newsletter/2021/march/stn-2021-03-mathys/) - spreadsheet complexity management
- [Lakera: LLM Hallucinations Guide](https://www.lakera.ai/blog/guide-to-hallucinations-in-large-language-models) - structured output hallucination patterns

### Tertiary (LOW confidence)
- [Medium: LLM Engineering Failure Modes 2025](https://medium.com/@gbalagangadhar/llm-engineering-in-2025-the-failure-modes-that-actually-matter-and-how-i-fix-them-ad1f6f1da77e) - community patterns, not verified against VIP30 stack
- General insurance litigation expert witness standards (synthesized from multiple search results on expert testimony credibility)
