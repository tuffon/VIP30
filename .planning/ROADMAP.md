# Roadmap: VIP30 v1.2 Launch Ready

## Overview

v1.2 transforms VIP30 from a functional MVP to a launch-ready product. The landing page gets a professional B2B redesign with concrete Xactimate-focused messaging, proof artifacts (screenshots, sample output), and trust elements (legal, security). The app experience is polished with user dropdowns, session persistence, and credits display. Production observability is added with structured logging and health checks.

## Phases

**Phase Numbering:**
- Phases 1-4: v1.1 MVP Launch (shipped)
- Phases 5-8: v1.2 Launch Ready (current)

- [ ] **Phase 5: Landing Page Redesign** - Enterprise B2B aesthetic with concrete Xactimate messaging
- [ ] **Phase 6: Proof Artifacts & Trust Footer** - Screenshots, sample output, legal/security footer
- [ ] **Phase 7: App Logged-In Experience** - User dropdown, session persistence, credits display
- [ ] **Phase 8: Observability** - Structured logging and health checks

## Phase Details

### Phase 5: Landing Page Redesign
**Goal**: Enterprise B2B landing page with concrete Xactimate messaging and professional design
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: HERO-01, HERO-02, HERO-03, HERO-04, NAV-01, DESIGN-01, DESIGN-02, DESIGN-03, DESIGN-04, DESIGN-05, DESIGN-06, DESIGN-07
**Success Criteria** (what must be TRUE):
  1. Hero clearly states "Turn two Xactimate estimate PDFs into a carrier vs contractor comparison in minutes"
  2. Feature labels use buyer language (deltas, mismatch flags, narrative citations)
  3. CTAs are consistent sitewide: "Generate Bid Comp" (primary) + "Book demo" (secondary)
  4. Messaging clearly indicates Xactimate-only support
  5. PDF→ESX removed from main navigation
  6. Design conveys enterprise B2B insurance tech (restrained colors, strong typography, generous whitespace, grid alignment)
  7. Real product UI screenshots are visual focal point (no stock imagery)
**Research**: Unlikely (internal frontend work)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Proof Artifacts & Trust Footer
**Goal**: Build trust with screenshots, sample output, and legal/security footer
**Depends on**: Phase 5 (landing page structure exists)
**Requirements**: PROOF-01, PROOF-02, PROOF-03, PROOF-04, PROOF-05, PROOF-06
**Success Criteria** (what must be TRUE):
  1. Landing page displays real product screenshots (delta table, narrative section, XLSX preview)
  2. User can download a redacted sample XLSX report
  3. Footer includes Privacy Policy link (page exists)
  4. Footer includes Terms of Service link (page exists)
  5. Footer includes Security overview (encryption, data handling)
  6. Footer includes company contact info
**Research**: Unlikely (static content)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

### Phase 7: App Logged-In Experience
**Goal**: Polish app UX with user dropdown, session persistence, and credits display
**Depends on**: Nothing (independent of landing page work)
**Requirements**: APP-01, APP-02, APP-03, APP-04
**Success Criteria** (what must be TRUE):
  1. Logged-in users see user dropdown in top-right nav with email and settings placeholder
  2. Clear visual distinction between logged-in and logged-out states across app
  3. Bid Comp UI displays actual credit balance from backend
  4. User sessions persist via localStorage until explicit logout
**Research**: Unlikely (React state, localStorage patterns)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

### Phase 8: Observability
**Goal**: Production monitoring with structured logging and health checks
**Depends on**: Nothing (independent of other phases)
**Requirements**: OBS-01, OBS-02
**Success Criteria** (what must be TRUE):
  1. API requests logged as structured JSON with request IDs
  2. /health endpoint returns service status for Render monitoring
**Research**: Unlikely (Python logging, FastAPI patterns)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD

## Progress

**Execution Order:**
Phases 5-8 (v1.2), continuing from v1.1's Phases 1-4.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Landing Page Redesign | 0/? | Not started | - |
| 6. Proof Artifacts & Trust | 0/? | Not started | - |
| 7. App Logged-In Experience | 0/? | Not started | - |
| 8. Observability | 0/? | Not started | - |
