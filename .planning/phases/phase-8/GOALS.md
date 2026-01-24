# Phase 8: Narrative Regression Fixes

**Goal:** Fix regressions in narrative output where category delta values are missing and narrative quality needs improvement

## Issues to Address

### 1. Missing Category Delta Values
The key_drivers in the output are missing `primary_total`, `comparison_total`, and `delta_total` numeric values. The pipeline's `DriverNarrative` model only captures an `amounts` string, but the export needs actual numbers for the xlsx output.

**Root cause:** `_convert_pipeline_result` sets these to `None` instead of carrying forward the `top_deltas` data.

### 2. Narrative Structure Needs Two Sentences
Each driver narrative should have:
- Sentence 1: General assessment of the delta amount
- Sentence 2: Focused assessment of the primary cause

**Current state:** Single narrative sentence without structured cause analysis.

### 3. Overview Too Short
Overview section needs 2-3 sentences covering:
- General delta of entire document
- Primary causes of the overall delta
- Assumptions/ideas behind the cause

**Current state:** Overview is too brief, lacks depth on cause analysis.

### 4. Estimate ID Names
Primary and Comparison estimates should be clearly identified by their ID names (filenames/estimate_names) throughout the output.

## Success Criteria

- [ ] Key drivers show Primary value, Comparison value, and Delta (all numeric)
- [ ] Each driver narrative has two sentences (delta assessment + cause assessment)
- [ ] Overview is 2-3 sentences with delta direction, primary causes, and reasoning
- [ ] Estimate names are prominently displayed and used in comparative framing
- [ ] All existing tests continue to pass
- [ ] New tests validate the improved output structure
