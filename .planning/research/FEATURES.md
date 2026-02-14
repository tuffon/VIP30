# Features Research: v1.1 MVP Launch

**Researched:** 2026-02-13
**Domain:** Email OTP auth, credit-based billing, workspace model
**Confidence:** HIGH (verified against industry standards and multiple sources)

## Executive Summary

Credit-based SaaS with email OTP authentication is a well-established pattern in 2025, with 67% of SaaS companies now using usage-based pricing and credits becoming the dominant pricing trend (126% YoY growth). The research validates the decisions already made (email OTP over magic links, ledger-style credits, charge on completion only) and provides specific implementation parameters. Key findings: 6-digit OTP codes with 5-10 minute expiry, graduated low-balance alerts at 25%/10%/5% remaining, and clear usage dashboards showing credit balance + consumption history are table stakes.

## Table Stakes (Must Have)

### Email OTP Auth

| Feature | Expected Behavior | Complexity | Source Confidence |
|---------|-------------------|------------|-------------------|
| **6-digit numeric code** | Standard length balances usability (easy to type) with security (1M combinations). 8-digit adds entropy but reduces usability. | Low | HIGH |
| **5-10 minute code expiry** | Industry standard. Shorter (30-60s) for high-security; 5-10 min for email delivery delays. | Low | HIGH |
| **Single-use invalidation** | Code must be marked as used immediately after successful verification. Prevents replay attacks. | Low | HIGH |
| **Rate limiting: code requests** | Max 3-5 OTP requests per email per 15 minutes. Prevents OTP flooding/abuse. | Medium | HIGH |
| **Rate limiting: verification attempts** | Max 5 attempts per code. After exhaustion, require new code. Lock account temporarily after 3 failed codes. | Medium | HIGH |
| **Specific error messages** | "Code expired" vs "Invalid code" vs "Too many attempts". Users need actionable feedback. | Low | HIGH |
| **Hash stored codes** | Never store OTP in plain text. Use SHA256 or bcrypt. | Low | HIGH |
| **Login metadata capture** | Store last_login_at, login_ip, login_method for security audit trail. | Low | HIGH |

**Dependencies:** Database (PostgreSQL), email sending (already have via existing stack)

### Credit System

| Feature | Expected Behavior | Complexity | Source Confidence |
|---------|-------------------|------------|-------------------|
| **Credit balance display** | Show current balance prominently in UI. Users must always know their remaining credits. | Low | HIGH |
| **Ledger-style tracking** | Separate credit_grants (additions) and credit_consumptions (deductions) tables. Immutable records. | Medium | HIGH |
| **Charge on completion only** | Deduct credits only when job succeeds. Failed jobs = no charge. Already decided. | Medium | HIGH |
| **Low balance alerts** | Graduated warnings at 25%, 10%, 5% remaining (or absolute thresholds like 2 credits, 1 credit). In-app notification minimum; email optional. | Medium | HIGH |
| **Consumption visibility** | Users see what consumed their credits: job ID, timestamp, amount. | Medium | HIGH |
| **Trial credits on signup** | Grant configurable default credits (5 for early adopters, 3 later). Single credit_grant record with source="signup_bonus". | Low | HIGH |
| **Credit expiry (MVP: none)** | Many systems have credit expiry. For MVP, credits don't expire. Simpler implementation. | Low | MEDIUM |

**Dependencies:** Database, workspace model (credits belong to workspace)

### Workspace Model

| Feature | Expected Behavior | Complexity | Source Confidence |
|---------|-------------------|------------|-------------------|
| **1 user per workspace (MVP)** | Simple model: user creates workspace on signup, workspace owns credits and jobs. Architecture supports future multi-user. | Low | HIGH |
| **Workspace-scoped data** | All jobs belong to workspace. All credit grants/consumptions belong to workspace. User is "member of" workspace. | Medium | HIGH |
| **workspace_id on all tables** | Standard multi-tenant pattern: every query includes workspace_id. Prevents data leakage. | Medium | HIGH |
| **No workspace switching (MVP)** | User has one workspace. No UI for switching. Architecture allows it later. | Low | HIGH |

**Dependencies:** Database schema design

### Job State Machine

| Feature | Expected Behavior | Complexity | Source Confidence |
|---------|-------------------|------------|-------------------|
| **Defined states** | queued, parsing, analyzing, writing, completed, failed. Clear progression. | Low | HIGH |
| **Progress indicator** | Show current state + percentage or step index. Users need to know job is progressing. | Medium | HIGH |
| **Error reason capture** | On failure, store human-readable error_reason. Display to user. | Low | HIGH |
| **Retry without double-charge** | Failed jobs can be retried. Since charge only on success, no refund logic needed. | Low | HIGH |
| **Clear failure messaging** | "Parsing failed: could not extract data from PDF" not "Job failed". Actionable. | Low | HIGH |

**Dependencies:** Database, credit system (for charge-on-success integration)

### Usage Tracking

| Feature | Expected Behavior | Complexity | Source Confidence |
|---------|-------------------|------------|-------------------|
| **Job history list** | Show recent jobs with status, date, credit cost (if completed). | Medium | HIGH |
| **Credit transaction history** | Show grants and consumptions with timestamps. Like a bank statement. | Medium | HIGH |
| **Current balance** | Prominent display of remaining credits. | Low | HIGH |

**Dependencies:** Database, credit system

## Differentiators (Nice to Have)

| Feature | Why It Helps | Complexity | Priority |
|---------|--------------|------------|----------|
| **Email notifications for low balance** | Proactive engagement, reduces surprise "no credits" moments. | Medium | P2 |
| **Daily bonus credits** | Pattern from Lovable: monthly limit + daily bonuses encourages consistent usage. | Medium | P3 |
| **Credit top-up before depletion** | Auto-purchase when balance hits threshold. Requires payment integration. | High | P3 |
| **Usage analytics dashboard** | Show trends: jobs per week, credits consumed over time. | Medium | P3 |
| **Session device binding** | OTP only valid if opened on same device/browser that requested it. Prevents interception. | Medium | P2 |
| **Multi-channel OTP delivery** | Fallback to SMS if email fails. Requires SMS provider. | High | P3 |
| **IP-based rate limiting** | Supplement email-based rate limiting with IP tracking. Prevents distributed abuse. | Medium | P2 |

## Anti-Features (Do NOT Build for MVP)

| Feature | Why Not Now |
|---------|-------------|
| **Magic links** | Already decided: email OTP preferred. Magic links have UX issues (tab switching, antivirus prefetch, device mismatch). Kinde's research supports OTP. |
| **OAuth (Google/Facebook)** | Adds complexity, dependency on third parties. Email OTP sufficient for MVP validation. |
| **Multi-user workspaces** | MVP is 1 user = 1 workspace. Architecture supports later. Don't build invitation flow, role permissions, or workspace switching. |
| **Credit expiry** | Adds complexity, customer confusion, support burden. Credits don't expire for MVP. |
| **Real-time credit deduction** | Pre-deduct on job start, refund on failure adds complexity. Charge-on-completion simpler and already decided. |
| **Payment/billing integration** | MVP uses granted credits only. No Stripe, no credit card, no purchases. Validate product first. |
| **8-digit OTP codes** | More secure but worse UX. 6-digit is industry standard and sufficient. |
| **SMS OTP** | Email-only for MVP. SMS requires provider integration, phone number collection. |
| **Passkeys/WebAuthn** | Future standard, but adds significant complexity. Email OTP is table stakes. |
| **CAPTCHA on OTP requests** | Only needed if abuse becomes a problem. Start without, add if needed. |
| **Workspace roles/permissions** | 1 user per workspace means no roles needed. Owner is implicit. |
| **Credit transfer between workspaces** | No multi-user, no transfers. Way out of scope. |
| **Advanced dunning/retry logic** | No payments = no failed payment recovery needed. |

## Feature Dependencies

```
Database (PostgreSQL)
    |
    +-- Workspace Model
    |       |
    |       +-- Credit System (credits belong to workspace)
    |       |       |
    |       |       +-- Job State Machine (charge on completion)
    |       |       |
    |       |       +-- Usage Tracking (shows credit history)
    |       |
    |       +-- Email OTP Auth (user belongs to workspace)
    |
    +-- Login Metadata (audit trail)
```

**Implementation order:**
1. Database + schema (foundation)
2. Workspace model (owns everything)
3. Email OTP auth (user can log in)
4. Credit system (grants on signup)
5. Job state machine (integrates with credits)
6. Usage tracking (displays everything)

## Specific Implementation Parameters

### Email OTP

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Code length | 6 digits | Industry standard, balances security/UX |
| Code expiry | 10 minutes | Accounts for email delivery delays |
| Max verification attempts | 5 per code | Then require new code |
| Max code requests | 5 per email per hour | Prevents flooding |
| Lockout after | 3 failed codes | Temporary 15-minute lockout |
| Code storage | SHA256 hash | Never plain text |

### Credit System

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Default credits (early) | 5 | Configurable via env var |
| Default credits (later) | 3 | Configurable via env var |
| Cost per job | 1 credit | Simple, predictable |
| Low balance alert | 2 credits remaining | Or 25% of initial grant |
| Critical balance alert | 1 credit remaining | Final warning |
| Credit expiry | Never (MVP) | Simplicity |

### Workspace Model

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Users per workspace | 1 (MVP) | Architecture supports N |
| Workspaces per user | 1 (MVP) | No switching UI needed |
| Workspace creation | Auto on signup | User doesn't choose |

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Email OTP parameters | HIGH | Multiple sources agree (Kinde, Prelude, Auth0, industry standards) |
| Credit system patterns | HIGH | Well-documented in 2025 SaaS pricing literature (Orb, Metronome, m3ter) |
| Workspace model | HIGH | Standard multi-tenant patterns (WorkOS, Logto, Frontegg) |
| Job state machine | HIGH | Standard async job patterns, internal to this codebase |
| Anti-features list | HIGH | Based on explicit project decisions + complexity analysis |
| Trial credit amounts | MEDIUM | Varies widely by product; 3-5 is reasonable for testing |

## Sources

### Primary (HIGH confidence)
- [Kinde: Why OTPs beat magic links](https://kinde.com/blog/security/why-kinde-likes-otps-better-than-magic-links/)
- [Prelude: Secure OTP Systems 2025](https://prelude.so/blog/secure-otp)
- [MojoAuth: OTP Expiration Best Practices](https://mojoauth.com/ciam-qna/best-practices-otp-expiration-retry-policies)
- [Unkey: Rate Limiting OTP Endpoints](https://www.unkey.com/blog/ratelimiting-otp)
- [ColorWhistle: SaaS Credits System Guide 2026](https://colorwhistle.com/saas-credits-system-guide/)
- [Orb: Trial Pricing Strategy Guide](https://www.withorb.com/blog/trial-pricing-strategy-guide)
- [m3ter: Credit Models in SaaS Pricing](https://www.m3ter.com/guides/credit-models-in-saas-pricing)
- [WorkOS: Multi-tenant Architecture Guide](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture)
- [Logto: Multi-tenant SaaS Guide](https://blog.logto.io/build-multi-tenant-saas-application)
- [Flightcontrol: Multi-tenant Data Modeling](https://www.flightcontrol.dev/blog/ultimate-guide-to-multi-tenant-saas-data-modeling)

### Secondary (MEDIUM confidence)
- [Scalekit: OTP vs Magic Links](https://www.scalekit.com/blog/otp-vs-magic-links-passwordless-authentication)
- [PricingSaaS: The Rise of SaaS Credit Models](https://newsletter.pricingsaas.com/p/how-to-use-credit-models-12-examples)
- [Inflection.io: Trial Strategies](https://www.inflection.io/post/time-based-trial-or-free-credits-choosing-the-right-trial-strategy)
- [Maxio: Consumption-Based Billing Guide](https://www.maxio.com/blog/consumption-based-billing)
- [Metronome: State of Usage-Based Pricing 2025](https://metronome.com/state-of-usage-based-pricing-2025)

---
*Research conducted for v1.1 MVP Launch milestone. Validates existing decisions and provides implementation parameters.*
