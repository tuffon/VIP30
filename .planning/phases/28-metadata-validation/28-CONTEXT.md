# Phase 28: Metadata + Validation - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<vision>
## How This Should Work

Phase 28 closes out v2.5 by completing two jobs: fix StateFarm metadata extraction (insured name, price list, address are all null today), then regenerate the golden masters carefully before confirming all 12 tests green.

The end state is clean but deliberate — not a batch-and-forget regeneration. Before any golden master is committed, surface the diff so I can see what changed and confirm it makes sense. The parser fixes in Phase 26 and 27 changed the parser significantly; the golden masters need to reflect the new reality but I want to see the delta first.

There's also a known gap to investigate: SF_BSchacter extracts 30/31 sections — one section still has no items. Understand the root cause. If it's a quick fix, close it in Phase 28. If it's complex or systemic, document it clearly and defer to Phase 29.

</vision>

<essential>
## What Must Be Nailed

- **Deliberate golden master regen** — diffs surfaced for review before committing; no blind overwrite of all 4 golden masters
- **StateFarm metadata populated** — insured_name, price_list, property_address extracted and showing up in parser output (currently all null)
- **SF_BSchacter gap investigated** — root cause of the 1 remaining section understood; fixed inline if it's a quick win, documented and deferred if complex
- **All 12 tests green** — the definitive success signal for v2.5

</essential>

<specifics>
## Specific Ideas

- Show the golden master diff (section count delta, item count delta, key field changes) as a summary before committing — enough detail to spot anything unexpected without reading every line
- If the SF_BSchacter gap is another token/format quirk like the asterisk fix, fix it. If it requires structural parser changes, document it and scope a Phase 29.
- The metadata fix should use the pdfplumber pattern established in Phase 24-02 (two-column summary page, page 3 extraction) — that approach already worked for manual golden master creation

</specifics>

<notes>
## Additional Context

- bschacter.golden.json needs updating from Phase 26's new 29-section output (was 0 sections in Phase 24-02 version)
- lachman_sf, kalyvas_sf, SF_BSchacter golden masters need updating from Phase 27's full item extraction
- customer_copy golden master may also need checking — it was created by pdfplumber in Phase 24-02, but the parser may now extract it differently
- The golden master regen is the last step before v2.5 is truly done; the diff review is the quality gate

</notes>

---

*Phase: 28-metadata-validation*
*Context gathered: 2026-03-09*
