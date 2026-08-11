# E2E personas & fixtures

Playwright drives **multiple logins** via `storageState` files under `e2e/.auth/`.

## Password policy (important)

| OK | Not OK |
|----|--------|
| Passwords in gitignored `e2e/.env` | Committing `e2e/.env` |
| Shared local password for `e2e.*` users | Using these users/passwords on production |
| `e2e/.env.example` with placeholders | Putting real prod credentials in the repo |

I set the shared E2E password to **`E2eTestPass!26`** (see your local `e2e/.env`). Admin stays **`password`** (existing site admin). Change anytime in `.env` + re-run seed / auth setup.

## Seed users (once per site)

```bash
cd /path/to/frappe-bench
E2E_PASSWORD='E2eTestPass!26' bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas
```

Creates users, employees, designations, and Reports To chain:

`employee / employee_b / associate / unpaid → manager → director → chair`

| Alias | Email | Roles / designation |
|-------|-------|---------------------|
| employee | e2e.employee@sevamrita.local | Employee / Associate |
| employee_b | e2e.employee.b@sevamrita.local | Employee / Associate |
| associate | e2e.associate@sevamrita.local | Employee / Associate |
| manager | e2e.manager@sevamrita.local | Employee / Manager |
| director | e2e.director@sevamrita.local | Employee / Director |
| chair | e2e.chair@sevamrita.local | NGO Board Chairperson |
| hr | e2e.hr@sevamrita.local | HR Manager |
| accounts | e2e.accounts@sevamrita.local | Accounts Manager |
| unpaid | e2e.unpaid@sevamrita.local | Employee / Unpaid type |
| admin | Administrator | existing |

## Use a persona in a spec

```ts
import { personaStorage } from '../helpers/personas';

test.describe('as employee', () => {
  test.use({ storageState: personaStorage('employee') });
  test('…', async ({ page }) => { /* logged in as Emp A */ });
});
```

Multi-step (Emp → Manager): open a second context with `browser.newContext({ storageState: personaStorage('manager') })`.

## Extra fields for spreadsheet cases (kept in e2e docs)

| Field | Example |
|-------|---------|
| Actors | `employee → manager → accounts` |
| Login per step | Steps 1–3 employee; 4–5 manager |
| Fixture data | amounts, leave type, T / T+N dates |
| Cleanup | cancel created docs |
| Layer | `ui` / `api` / `ops` / `python` |

See `docs/e2e-coverage.md` for ID → status.

## Seeing the browser

```bash
cd apps/volunteering
yarn test:e2e:headed --grep @persona   # visible Chromium
yarn test:e2e:ui                       # interactive UI Mode
```
