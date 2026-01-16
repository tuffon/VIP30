# Coding Conventions

**Analysis Date:** 2026-01-15

## Naming Patterns

**Files:**
- TypeScript/React: `camelCase.tsx` for components, `camelCase.ts` for modules
- Component files: PascalCase named exports, e.g., `LandingSignupForm.tsx` exports `LandingSignupForm`
- Page files: `page.tsx` (Next.js App Router convention)
- Python: `snake_case.py` for all modules
- Test files: `test_*.py` (Python) or `*.test.tsx` (TypeScript)

**Functions:**
- TypeScript: `camelCase` for all functions, e.g., `handleSubmit`, `makeStore`
- React components: `PascalCase`, e.g., `LandingSignupForm`, `NavAuth`
- Python: `snake_case` for all functions, e.g., `normalize_money`, `get_bucket`

**Variables:**
- TypeScript: `camelCase`, e.g., `carrierFile`, `jobStatus`, `apiBase`
- Constants: `UPPER_CASE` or `camelCase` depending on scope (inline constants use camelCase)
- Python: `snake_case`, e.g., `_cors_origins`, `_log_level`
- Private Python variables: Leading underscore, e.g., `_redis_url`, `_r`, `_q`

**Types:**
- TypeScript: `PascalCase` for types and interfaces
- Union types for state: `type Status = "idle" | "loading" | "success" | "error"`
- Props types: `type Props = { ... }` defined inline before component
- Python: Type hints using `typing` module with `Optional`, `Dict`, `List`, etc.

## Code Style

**Formatting:**
- Prettier with `printWidth: 100`, `semi: true`, `singleQuote: false`
- Config: `.prettierrc` at root

**Linting:**
- ESLint with TypeScript parser and recommended rules
- Next.js app uses `next/core-web-vitals` preset
- Config: `.eslintrc.cjs` at root and per-app
- Python: `noqa` comments used for specific rule suppression, e.g., `# noqa: BLE001`

**TypeScript:**
- Strict mode enabled (`"strict": true` in tsconfig)
- Target: ES2022
- Module resolution: Bundler

## Import Organization

**Order (TypeScript):**
1. Framework imports (`react`, `next/*`, `next-auth/*`)
2. External library imports (`@reduxjs/toolkit`, `@tanstack/react-query`)
3. Internal/relative imports (`../components/*`, `./services/*`)
4. Type imports (often inline)

**Order (Python):**
1. `from __future__ import` (when used)
2. Standard library imports
3. Third-party imports
4. Local imports from `src.*`

**Path Aliases:**
- `@/*` maps to app root (Next.js apps)
- `@shared/*` maps to `packages/shared/*`

## Error Handling

**TypeScript/React Patterns:**
```typescript
try {
  const resp = await fetch(endpoint, { method: "POST", ... });
  if (!resp.ok) {
    throw new Error(`Operation failed (${resp.status})`);
  }
  // success handling
} catch (err) {
  setStatus("error");
  setMessage(err instanceof Error ? err.message : "Unexpected error");
}
```

**Python/FastAPI Patterns:**
```python
try:
    result = some_operation()
except Exception as e:  # noqa: BLE001
    logger.error("Operation failed: %s", e)
    raise HTTPException(status_code=500, detail=str(e))
```

- Use `HTTPException` for API errors with appropriate status codes
- Broad `except Exception` catches are acceptable with noqa comment and logging

## Logging

**Framework (TypeScript):** Console logging via browser devtools (no structured logging framework)

**Framework (Python):**
- Standard library `logging` module
- Logger per module: `logger = logging.getLogger("vip-parse.api")`
- Format: `"%(asctime)s %(levelname)-8s %(name)s :: %(message)s"`

**Patterns:**
```python
logger.info("Operation completed: job_id=%s status=%s", job_id, status)
logger.warning("Config not set; feature disabled")
logger.error("Operation failed: job_id=%s error=%s", job_id, err)
```

## Comments

**When to Comment:**
- Complex business logic (Xactimate parsing rules)
- Non-obvious regex patterns
- Environment variable fallback chains
- Compatibility workarounds (e.g., next-auth version notes)

**JSDoc/TSDoc:**
- Not widely used; minimal inline comments preferred
- Python: Docstrings for public module/class functions

## Function Design

**Size:**
- Prefer small, focused functions
- Larger functions acceptable for complete workflows (e.g., form submission handlers)

**Parameters:**
- TypeScript: Destructured props for React components
- Python: Keyword arguments with type hints for clarity

**Return Values:**
- TypeScript: Explicit return types not required (inferred)
- Python: Return type hints on public functions

## Module Design

**Exports (TypeScript):**
- Named exports preferred: `export function ComponentName()`
- Default exports for Next.js pages: `export default function PageName()`

**Exports (Python):**
- Module-level variables and functions
- `__all__` used sparingly for re-exports

**Barrel Files:**
- `packages/shared/src/index.ts` re-exports shared types/constants
- Python `__init__.py` files used for package exports

## React Patterns

**State Management:**
- Local state: `useState` with explicit type unions for status
- Global state: Redux Toolkit with RTK Query for API caching
- Session: `next-auth/react` hooks (`useSession`)

**Component Structure:**
```typescript
"use client";

import { useState, useCallback, useMemo } from "react";

type Props = { ... };
type Status = "idle" | "loading" | "success" | "error";

export function ComponentName({ prop1, prop2 }: Props) {
  const [state, setState] = useState<Status>("idle");

  const handler = useCallback(async () => { ... }, [deps]);
  const computed = useMemo(() => ..., [deps]);

  return <div>...</div>;
}
```

**Hooks Usage:**
- `useCallback` for event handlers passed to children
- `useMemo` for expensive computations and stable references
- `useEffect` for sync with external systems

## Styling

**Framework:** Tailwind CSS

**Patterns:**
- Utility classes inline on elements
- Conditional classes via template literals: `` `${condition ? "class-a" : "class-b"}` ``
- Design tokens in `tailwind.config.ts` for brand colors

**Example:**
```tsx
<button
  className="rounded-full bg-slate-900 px-8 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
>
```

## Python Specific

**Dataclasses:**
- Use `@dataclass` for structured data with type hints
- Field defaults via `field(default_factory=list)`

**Type Hints:**
```python
from typing import Dict, List, Optional, Sequence

def process(input_pdf: Path, output_pdf: Optional[Path] = None) -> PreflightResult:
```

**String Formatting:**
- f-strings for simple interpolation
- `%s` style for logging (lazy evaluation)

---

*Convention analysis: 2026-01-15*
