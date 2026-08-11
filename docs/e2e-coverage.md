# E2E coverage matrix

Source of truth for cases: `sevamrit-erp-testing.xlsx` (sheet `test-cases`, 108 rows).

Status values: `not started` | `automated` | `python-covered` | `ops` | `partial`

| Test Case ID | Layer | Spec / module | Status |
|--------------|-------|---------------|--------|
| AC-BUD-004 | Playwright UI (SPA) | `e2e/tests/budget-health.spec.ts` | automated |
| AC-ADV-009 | Playwright UI (SPA) | `e2e/tests/advances.spec.ts` | automated |
| (ops smoke) | Ops | `e2e/tests/smoke.spec.ts` | automated |
| (API budget/advances) | API | `e2e/tests/api/volunteering-api.spec.ts` | automated |
| AC-BKS-003 | Playwright UI (Desk) | `e2e/tests/desk/desk-smoke.spec.ts` | partial (`/desk/my-expenses`) |
| HR-DWL-013 | Playwright UI (Desk) | `e2e/tests/desk/desk-smoke.spec.ts` | partial (`/desk/my-work`) |
| HR-DWL-* | Desk / Python | — | not started |
| HR-WFH-* | Desk / Python / Ops | — | not started |
| HR-LV-* | Desk / Python | — | not started |
| HR-ATT-* | Python / Ops | — | not started |
| HR-MGR-* | Desk | — | not started |
| HR-CFG-* | Desk / Python | — | not started |
| AC-VEN-* | Desk / Python | — | not started |
| AC-ADV-001…008, 010–011 | Desk / Python | — | not started |
| AC-CLM-* | Desk / Python | — | not started |
| AC-APR-* | Desk / Python | — | not started |
| AC-SET-* | Desk / Python | — | not started |
| AC-BUD-001…003 | Python / Desk | existing `test_accounting_budget.py` etc. | python-covered (partial) |
| AC-BKS-* (other) | Desk / Ops | — | not started |
| XM-* | Desk | — | not started |

Convention: Playwright `test()` titles start with the spreadsheet ID when a row is mapped (`AC-BUD-004: …`).

## Multi-persona

See [e2e-personas.md](./e2e-personas.md). Dedicated users are seeded on `sevamrita.local` (`e2e.*@sevamrita.local`). Specs switch with `personaStorage('employee'|'manager'|…)`.

| Check | Spec | Status |
|-------|------|--------|
| Employee + Manager login | `e2e/tests/persona-smoke.spec.ts` | automated |
