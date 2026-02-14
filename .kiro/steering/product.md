# Product Overview

VIP30 is a SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with professional adjuster-tone narrative analysis explaining the differences.

## Core Value Proposition

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Key Features

- Xactimate PDF parsing with structured data extraction
- Asynchronous job queue processing for long-running tasks
- Secure file upload/download via presigned URLs
- XLSX report generation with comparison data
- LLM-powered narrative generation with adjuster tone control
- Three-pass LLM pipeline (Analysis → Writer → Compliance rewrite)
- Six deterministic quality gates for narrative quality
- Pass-level Redis caching with content-hash keys

## Current Version

v1.0.1 shipped 2026-02-09

## Target Users

Insurance adjusters who need to compare Xactimate estimates and produce professional reports explaining bid differences.
