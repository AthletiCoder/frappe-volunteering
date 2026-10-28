# Portal regression tests

Run against an isolated LOCAL COPY of `sevamrita.local`, not production or an
existing demo that needs to stay unchanged. The desktop suite creates real
projects, advances, claims, donations, purchase receipts/invoices/payments,
opening balances and user/employee records. It refuses non-local base URLs.
Keep outgoing email, email sync, the scheduler and workers disabled on the copy.
Use its own admin password and `E2E_AUTH_DIR`; never reuse production sessions.

```sh
npm run test:e2e:portal
npm run test:e2e:portal:mobile
npm run test:e2e:purchasing
npm run test:frontend
```

Set `BASE_URL` to the isolated site's port (for example,
`http://127.0.0.1:8002`), along with `E2E_ADMIN_PASSWORD`, `E2E_PASSWORD`,
`E2E_PROJECT_PASSWORD`, and a separate `E2E_AUTH_DIR`. Both suites default to
port 8001 if omitted. Run the live desktop and mobile suites sequentially;
concurrent same-user logins are tested explicitly, not hidden by retries.
Set `PORTAL_REPORT_NAME=portal-regression-followup` for a targeted desktop rerun
without overwriting the original evidence.

The copied database must have the existing E2E, project-demo and purchasing-demo
personas/masters. Run `e2e_api.ensure_fixtures` as Administrator on the copy to
refresh the common E2E project, employee hierarchy and bank fixtures. The
purchasing lifecycle uses the `demo.purchase.*` users, the Pune Community Kitchen
training project and Demo Purchasing Bank; these are included in the demo copy.
Do not weaken the local-only demo-seeder guards to seed a remote site.

The desktop suite covers role-based navigation; project proposal, approval and
financial visibility; advance requests, hierarchy, freezes, disbursement and
returns; bank-account approval; invoice creation and signatures; single- and
multi-invoice claims; receipt review, approval, classification and payment;
general/CSR donations; and opening-balance form access and posting preview.
It also covers a real purchase from employee request through approval, supplier
advance, receipt, bill and final payment; private opening-balance proof and its
dated ledger; unused account maintenance; user/employee creation, linking and
password reset; fiscal-year creation/reactivation; Guest API denial; Home search;
two-device login concurrency; and actual signed combined-invoice submission,
signature invalidation and receipt correction/resubmission. The purchasing fixture suite separately checks
page/action isolation, UI validation and responsive layouts without live writes.
The mobile suite audits those forms and management workspaces at 360px and
390px, including the three purchasing pages and fiscal years, for clipped controls, horizontal overflow, small
primary targets and inputs that trigger mobile focus zoom.

Also run the Frappe backend suite from the local bench before deployment:

```sh
bench --site <isolated-test-site.local> run-tests --app volunteering --skip-before-tests --test-category unit
bench --site <isolated-test-site.local> run-tests --app volunteering --skip-before-tests --test-category integration
```

Do not interpret a browser-only pass as proof that backend accounting and
permission tests passed. Preserve the failing output and investigate any
backend crash or failure before release.

The older `playwright.config.ts` suite is separate. It includes legacy Desk
routes and vendor-payment scenarios that are not implemented in the current
Home portal. Its full run is not a substitute for the local-only portal suite,
and a portal-suite pass must not be described as a pass of every historical
Desk E2E spec.

`projects/layout.spec.ts` is a legacy Desk-only screen check and is explicitly
excluded from this Home gate. Backend HR/attendance, volunteering, donation API,
pledge API and accounting tests still run in the complete app backend suite.

## Evidence and interpretation

- Desktop: JSON and HTML under `test-results/<report-name>-*`, plus failure traces.
- Mobile: `test-results/mobile-results.json` and per-screen phone screenshots.
- Preserve first failures. Correct erroneous selectors/fixtures, rerun affected
  cases and distinguish harness corrections from application fixes.
- Do not skip or auto-retry known functional failures to claim a green gate.
- A mobile Chrome audit is not physical Android or iOS/Safari device testing.
- SMTP delivery, real bank transfers, live Cashfree/Interakt delivery and production
  hosting are not verified by local test fixtures.
- See `PORTAL_REGRESSION_REPORT_2026-10-27.md` for the recorded run and open defects.
- See `PORTAL_FIX_VERIFICATION_2026-10-27.md` for the subsequent fixes and complete passing rerun.
