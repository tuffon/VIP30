## ScopeVista Frontend

This app powers the ScopeVista landing page, Google-authenticated console, and bid comparison experience.

### Environment variables

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL for the FastAPI backend (e.g. `https://api.scopevista.com`). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth credentials for Google sign-in. |
| `NEXTAUTH_SECRET` | NextAuth encryption secret (`openssl rand -hex 32`). |

### Local development

```bash
cd apps/vipclaims-saas
pnpm install
pnpm dev
```

### Tests

The landing signup form is covered via Vitest + Testing Library.

```bash
pnpm test
```

### Backend integrations

* **Marketing captures** POST to `/marketing/signup` (requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` on the FastAPI side).
* **Document-ready emails** rely on SendGrid (`SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`) and are triggered from the worker once the XLSX is uploaded.

