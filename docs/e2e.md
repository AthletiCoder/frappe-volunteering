# Volunteering E2E (Playwright)

Browser / API / ops tests for the volunteering app. Run from Cursor with the [Playwright Test](https://marketplace.visualstudio.com/items?itemName=ms-playwright.playwright) extension or the scripts below.

## Prerequisites

1. Bench running: `bench start` (site reachable at `http://sevamrita.local:8000`)
2. Node deps + Chromium (once):

```bash
cd apps/volunteering
yarn install   # or npm install
npx playwright install chromium
```

3. Credentials (optional; local default is Administrator / password — override if needed):

```bash
export FRAPPE_USER=Administrator
export FRAPPE_PASSWORD=password
export BASE_URL=http://sevamrita.local:8000
```

## Scripts

| Command | Purpose |
|---------|---------|
| `yarn test:e2e` | Headless full suite |
| `yarn test:e2e:ui` | Playwright **UI Mode** (best in Cursor) |
| `yarn test:e2e:headed` | Visible browser |
| `yarn test:e2e:debug` | Step debugger |
| `yarn test:e2e:smoke` | `@smoke` ops checks only |
| `yarn test:e2e:desk` | `@desk` Wave 2 stubs |

## Layout

```
e2e/
  helpers/     auth, Frappe REST, routes
  pages/       page objects
  tests/       specs (titles start with spreadsheet Test Case IDs when mapped)
  .auth/       storageState + CSRF (gitignored)
```

## Spreadsheet coverage

See [e2e-coverage.md](./e2e-coverage.md) for Test Case IDs. Personas: [e2e-personas.md](./e2e-personas.md).

### Seed personas (required for Desk / multi-login)

```bash
E2E_PASSWORD='E2eTestPass!26' bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas
cp e2e/.env.example e2e/.env   # if needed; passwords stay local
```

## Adding a Desk test (Wave 2)

1. Put the file under `e2e/tests/desk/`.
2. Title the test with the spreadsheet ID, e.g. `HR-DWL-001: Create and submit daily work log`.
3. Tag with `@desk` (and `@smoke` if it is a cheap health check).
4. Prefer API helpers in `e2e/helpers/frappe.ts` for fixture setup/teardown; keep the browser path for the user-visible flow only.
5. Update `docs/e2e-coverage.md` status.
