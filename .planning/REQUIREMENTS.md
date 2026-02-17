# Requirements: VIP30 v1.2 Launch Ready

**Defined:** 2026-02-17
**Core Value:** Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## v1.2 Requirements

Requirements for v1.2 release. Each maps to roadmap phases.

### Landing Page - Hero & Messaging

- [x] **HERO-01**: Landing page hero clearly states "Turn two Xactimate estimate PDFs into a carrier vs contractor comparison in minutes"
- [x] **HERO-02**: Feature labels use buyer language (side-by-side deltas, mismatch flags, narrative citations)
- [x] **HERO-03**: CTAs are consistent sitewide: "Generate Bid Comp" (primary) + "Book demo" (secondary)
- [x] **HERO-04**: Messaging clearly indicates Xactimate-only support (not generic PDF)

### Landing Page - Proof & Trust

- [x] **PROOF-01**: Landing page displays screenshots (delta table, narrative section, XLSX preview)
- [x] **PROOF-02**: User can download a redacted sample XLSX report
- [x] **PROOF-03**: Footer includes Privacy Policy link
- [x] **PROOF-04**: Footer includes Terms of Service link
- [x] **PROOF-05**: Footer includes Security overview (encryption, data handling)
- [x] **PROOF-06**: Footer includes company contact info

### Landing Page - Navigation

- [x] **NAV-01**: PDF→ESX removed from main navigation (moved to roadmap card or hidden)

### Landing Page - Design

- [x] **DESIGN-01**: Restrained color palette (enterprise B2B aesthetic, not generic SaaS colors)
- [x] **DESIGN-02**: Strong typographic hierarchy with clear visual weight distinctions
- [x] **DESIGN-03**: Generous whitespace and consistent spacing throughout
- [x] **DESIGN-04**: Consistent grid alignment across all sections
- [x] **DESIGN-05**: Real product UI screenshots as visual focal point (not stock imagery or illustrations)
- [x] **DESIGN-06**: Remove generic gradients and cluttered visual elements
- [x] **DESIGN-07**: Overall aesthetic conveys high-trust insurance tech platform

### App Experience

- [x] **APP-01**: Logged-in users see user dropdown in top-right nav with email and settings placeholder
- [x] **APP-02**: Clear visual distinction between logged-in and logged-out states across app
- [x] **APP-03**: Bid Comp UI displays actual credit balance from backend
- [x] **APP-04**: User sessions persist via localStorage until explicit logout

### Observability

- [x] **OBS-01**: API requests logged as structured JSON with request IDs
- [x] **OBS-02**: /health endpoint returns service status for Render monitoring

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Landing Page

- **HERO-V2-01**: Demo video walkthrough (60 seconds)
- **PRICE-V2-01**: Pricing page with usage tiers and Team/Enterprise options
- **HERO-V2-02**: Clean Verisk language → "industry-standard categories"

### App Experience

- **APP-V2-01**: Date-range filtering for job/credit history

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| OAuth login | Email OTP sufficient for MVP |
| Multi-user workspaces | 1 user per workspace for now |
| Pricing restructure | Experimental 5 free credits model, discover pricing later |
| Demo video | Defer to v2, screenshots sufficient for v1.2 |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HERO-01 | Phase 5 | Complete |
| HERO-02 | Phase 5 | Complete |
| HERO-03 | Phase 5 | Complete |
| HERO-04 | Phase 5 | Complete |
| NAV-01 | Phase 5 | Complete |
| DESIGN-01 | Phase 5 | Complete |
| DESIGN-02 | Phase 5 | Complete |
| DESIGN-03 | Phase 5 | Complete |
| DESIGN-04 | Phase 5 | Complete |
| DESIGN-05 | Phase 5 | Complete |
| DESIGN-06 | Phase 5 | Complete |
| DESIGN-07 | Phase 5 | Complete |
| PROOF-01 | Phase 6 | Complete |
| PROOF-02 | Phase 6 | Complete |
| PROOF-03 | Phase 6 | Complete |
| PROOF-04 | Phase 6 | Complete |
| PROOF-05 | Phase 6 | Complete |
| PROOF-06 | Phase 6 | Complete |
| APP-01 | Phase 7 | Complete |
| APP-02 | Phase 7 | Complete |
| APP-03 | Phase 7 | Complete |
| APP-04 | Phase 7 | Complete |
| OBS-01 | Phase 8 | Complete |
| OBS-02 | Phase 8 | Complete |

**Coverage:**
- v1.2 requirements: 24 total
- Completed: 24 ✓
- Remaining: 0

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 — All requirements complete*
