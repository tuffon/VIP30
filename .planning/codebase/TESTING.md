# Testing Patterns

**Analysis Date:** 2026-01-15

## Test Frameworks

**TypeScript (vipclaims-saas):**
- Runner: Vitest 1.1.3
- Config: `apps/vipclaims-saas/vitest.config.ts`
- Environment: jsdom
- Assertion: Vitest built-in + @testing-library/jest-dom

**Python (vip-parse):**
- Runner: pytest
- Config: implicit (no pytest.ini found)
- Fixtures: pytest built-in fixtures

**Run Commands:**
```bash
# TypeScript (from vipclaims-saas directory)
pnpm test                    # Run all tests via vitest
pnpm vitest                  # Watch mode
pnpm vitest --coverage       # Coverage (if configured)

# Python (from vip-parse directory)
pytest                       # Run all tests
pytest tests/test_file.py    # Run specific file
pytest -v                    # Verbose output

# Monorepo root
pnpm test                    # Run all via turbo
```

## Test File Organization

**Location:**
- TypeScript: Co-located in `components/__tests__/` directory
- Python: Separate `tests/` directory at app root

**Naming:**
- TypeScript: `ComponentName.test.tsx`
- Python: `test_module_name.py`

**Structure:**
```
apps/vipclaims-saas/
  components/
    __tests__/
      LandingSignupForm.test.tsx
    LandingSignupForm.tsx

apps/vip-parse/
  tests/
    test_xactimate_parser.py
    test_pdf_preflight.py
    test_bid_comp_normalize.py
  src/
    ...
```

## Test Structure

**TypeScript/Vitest Suite Organization:**
```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ComponentName } from "../ComponentName";

describe("ComponentName", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("describes expected behavior", () => {
    render(<ComponentName prop="value" />);
    const element = screen.getByPlaceholderText("placeholder");
    expect(element.value).toBe("expected");
  });

  it("handles async operations", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    render(<ComponentName />);
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => expect(screen.getByText(/success/i)).toBeVisible());
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
```

**Python/pytest Suite Organization:**
```python
import pytest
from module import function_under_test

def test_basic_functionality():
    result = function_under_test("input")
    assert result == "expected"

def test_edge_case():
    assert function_under_test("") is None
    assert function_under_test(None) is None

def test_with_fixture(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("content")
    result = process_file(input_file)
    assert result.success
```

**Patterns:**
- Setup: `beforeEach` (TypeScript) or pytest fixtures (Python)
- Teardown: `vi.restoreAllMocks()` after each test
- Assertions: Direct assertions, no assertion library wrappers

## Mocking

**TypeScript/Vitest:**
```typescript
// Mock fetch globally
const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
  new Response(JSON.stringify({ status: "stored" }), { status: 200 }),
);

// Verify mock was called
expect(fetchMock).toHaveBeenCalledOnce();
```

**Python/pytest:**
```python
# Using monkeypatch fixture for module-level mocking
def test_with_mock(monkeypatch):
    monkeypatch.setattr(module, "function", lambda: "mocked")
    result = code_under_test()
    assert result == "expected"

# Recording mock for tracking calls
class RecordingProcessor:
    def __init__(self):
        self.calls = []

    def process(self, *args):
        self.calls.append(args)
        return default_result

def test_tracks_calls():
    processor = RecordingProcessor()
    code_under_test(processor)
    assert processor.calls == [expected_args]
```

**What to Mock:**
- External HTTP calls (fetch, API clients)
- File system operations (use `tmp_path` fixture in Python)
- Third-party library functions (pdfplumber, etc.)
- Environment-dependent behavior

**What NOT to Mock:**
- Internal business logic
- Pure functions being tested
- Data transformation utilities

## Fixtures and Factories

**Python Test Fixtures:**
```python
@pytest.fixture
def stub_pdf(monkeypatch):
    """Stub pdfplumber.open with controllable page text."""
    class DummyPage:
        def __init__(self, text):
            self._text = text
        def extract_text(self, layout=True):
            return self._text

    class DummyPDF:
        def __init__(self, pages):
            self.pages = [DummyPage(text) for text in pages]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _apply(pages):
        monkeypatch.setattr(pdfplumber, "open", lambda _: DummyPDF(pages))
    return _apply

def test_uses_fixture(tmp_path, stub_pdf):
    stub_pdf(["Page 1 text", "Page 2 text"])
    # test code here
```

**TypeScript Test Data:**
```typescript
// Inline test data defined in test file
const testProps = {
  apiBase: "http://localhost:4000",
  defaultEmail: "test@example.com",
};

render(<Component {...testProps} />);
```

**Location:**
- Python: Fixtures defined in test files or `conftest.py`
- TypeScript: Test data defined inline in test files

## Coverage

**Requirements:** No enforced coverage thresholds detected

**View Coverage:**
```bash
# TypeScript
pnpm vitest --coverage

# Python
pytest --cov=src --cov-report=html
```

## Test Types

**Unit Tests:**
- Parser functions (`test_xactimate_parser.py`)
- Normalization utilities (`test_bid_comp_normalize.py`)
- Component rendering (`LandingSignupForm.test.tsx`)

**Integration Tests:**
- PDF preflight pipeline (`test_pdf_preflight.py`)
- CLI entry points with mocked dependencies
- Component form submission with mocked fetch

**E2E Tests:**
- Not configured (no Playwright/Cypress detected)

## Common Patterns

**Async Testing (TypeScript):**
```typescript
it("waits for async operation", async () => {
  render(<Component />);
  fireEvent.click(screen.getByRole("button"));

  await waitFor(() => {
    expect(screen.getByText(/success/i)).toBeVisible();
  });
});
```

**Async Testing (Python):**
```python
# Tests are synchronous; async code tested via sync wrappers
def test_sync_wrapper():
    result = sync_function_that_calls_async()
    assert result.success
```

**Error Testing (TypeScript):**
```typescript
it("shows error on failure", async () => {
  vi.spyOn(global, "fetch").mockRejectedValue(new Error("Network error"));

  render(<Component />);
  fireEvent.submit(form);

  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeVisible();
  });
});
```

**Error Testing (Python):**
```python
def test_raises_on_invalid_input():
    with pytest.raises(ValueError):
        function_under_test(invalid_input)

def test_returns_none_on_bad_data():
    assert function_under_test("invalid") is None
```

**Parametric Testing (Python):**
```python
# Not heavily used, but pytest supports:
@pytest.mark.parametrize("input,expected", [
    ("$1,234.56", 1234.56),
    ("  ", None),
    (None, None),
])
def test_normalize_money(input, expected):
    assert normalize_money(input) == expected
```

## Testing Configuration

**Vitest Setup (`apps/vipclaims-saas/vitest.setup.ts`):**
```typescript
import "@testing-library/jest-dom/vitest";
```

**Vitest Config (`apps/vipclaims-saas/vitest.config.ts`):**
```typescript
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
```

## Test File Locations Summary

| App | Test Directory | Pattern | Framework |
|-----|----------------|---------|-----------|
| `apps/vipclaims-saas` | `components/__tests__/` | `*.test.tsx` | Vitest |
| `apps/vip-parse` | `tests/` | `test_*.py` | pytest |

## Adding New Tests

**TypeScript Component Test:**
1. Create `ComponentName.test.tsx` in `components/__tests__/`
2. Import from `@testing-library/react` and `vitest`
3. Use `describe`/`it` blocks with `render`, `screen`, `fireEvent`
4. Mock external dependencies with `vi.spyOn`

**Python Unit Test:**
1. Create `test_module.py` in `tests/`
2. Import function under test with `sys.path` manipulation if needed
3. Write `def test_*` functions with assertions
4. Use `pytest.fixture` for shared setup

---

*Testing analysis: 2026-01-15*
