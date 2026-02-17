# Requirements: VIP30 v1.2 Launch Ready

**Defined:** 2026-02-17
**Core Value:** Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## v1.2 Requirements

Requirements for v1.2 release. Each maps to roadmap phases.

### Landing Page - Hero & Messaging

- [ ] **HERO-01**: Landing page hero clearly states "Turn two Xactimate estimate PDFs into a carrier vs contractor comparison in minutes"
- [ ] **HERO-02**: Feature labels use buyer language (side-by-side deltas, mismatch flags, narrative citations)
- [ ] **HERO-03**: CTAs are consistent sitewide: "Generate Bid Comp" (primary) + "Book demo" (secondary)
- [ ] **HERO-04**: Messaging clearly indicates Xactimate-only support (not generic PDF)

### Landing Page - Proof & Trust

- [ ] **PROOF-01**: Landing page displays screenshots (delta table, narrative section, XLSX preview)
- [ ] **PROOF-02**: User can download a redacted sample XLSX report
- [ ] **PROOF-03**: Footer includes Privacy Policy link
- [ ] **PROOF-04**: Footer includes Terms of Service link
- [ ] **PROOF-05**: Footer includes Security overview (encryption, data handling)
- [ ] **PROOF-06**: Footer includes company contact info

### Landing Page - Navigation

- [ ] **NAV-01**: PDF→ESX removed from main navigation (moved to roadmap card or hidden)

### Landing Page - Design

- [ ] **DESIGN-01**: Restrained color palette (enterprise B2B aesthetic, not generic SaaS colors)
- [ ] **DESIGN-02**: Strong typographic hierarchy with clear visual weight distinctions
- [ ] **DESIGN-03**: Generous whitespace and consistent spacing throughout
- [ ] **DESIGN-04**: Consistent grid alignment across all sections
- [ ] **DESIGN-05**: Real product UI screenshots as visual focal point (not stock imagery or illustrations)
- [ ] **DESIGN-06**: Remove generic gradients and cluttered visual elements
- [ ] **DESIGN-07**: Overall aesthetic conveys high-trust insurance tech platform

### App Experience

- [ ] **APP-01**: Logged-in users see user dropdown in top-right nav with email and settings placeholder
- [ ] **APP-02**: Clear visual distinction between logged-in and logged-out states across app
- [ ] **APP-03**: Bid Comp UI displays actual credit balance from backend
- [ ] **APP-04**: User sessions persist via localStorage until explicit logout

### Observability

- [ ] **OBS-01**: API requests logged as structured JSON with request IDs
- [ ] **OBS-02**: /health endpoint returns service status for Render monitoring

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
| HERO-01 | TBD | Pending |
| HERO-02 | TBD | Pending |
| HERO-03 | TBD | Pending |
| HERO-04 | TBD | Pending |
| PROOF-01 | TBD | Pending |
| PROOF-02 | TBD | Pending |
| PROOF-03 | TBD | Pending |
| PROOF-04 | TBD | Pending |
| PROOF-05 | TBD | Pending |
| PROOF-06 | TBD | Pending |
| NAV-01 | TBD | Pending |
| DESIGN-01 | TBD | Pending |
| DESIGN-02 | TBD | Pending |
| DESIGN-03 | TBD | Pending |
| DESIGN-04 | TBD | Pending |
| DESIGN-05 | TBD | Pending |
| DESIGN-06 | TBD | Pending |
| DESIGN-07 | TBD | Pending |
| APP-01 | TBD | Pending |
| APP-02 | TBD | Pending |
| APP-03 | TBD | Pending |
| APP-04 | TBD | Pending |
| OBS-01 | TBD | Pending |
| OBS-02 | TBD | Pending |

**Coverage:**
- v1.2 requirements: 24 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 24

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after initial definition*
