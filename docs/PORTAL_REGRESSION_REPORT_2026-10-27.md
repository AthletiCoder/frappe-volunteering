# Portal regression report — 27 October 2026

**Follow-up:** the two defects below have since been fixed locally. See
[fix verification](PORTAL_FIX_VERIFICATION_2026-10-27.md) for the changes and rerun
results. This report preserves the original failing run.

**Result: testing completed; release gate is not green. Two reproducible functional defects remain.**

The latest result for 649 distinct test cases is **647 passed and 2 failed**.
Build checks also passed. This count combines the full backend runs, the complete
desktop run and explicit targeted follow-ups, the complete serial mobile run,
fixture-based purchasing tests, JavaScript unit tests and Android unit tests.
It is not a claim that a single 649-case command passed.

## Results

| Layer | Distinct cases | Passed | Failed | Interpretation |
| --- | ---: | ---: | ---: | --- |
| App backend unit and integration | 526 | 526 | 0 | 146 unit + 378 integration, then 2 additional ledger regressions; the latter module also repeated 4 existing tests successfully |
| Frontend unit | 9 | 9 | 0 | Navigation/role combinations and included-tax arithmetic/validation |
| Purchasing browser tests with deterministic API fixtures | 22 | 22 | 0 | Real Vue UI, mocked API responses; separate from database E2E |
| Live Home desktop browser cases | 69 | 67 | 2 | Latest result per case across full run and targeted follow-ups; no automatic retries |
| Mobile Home layout/interaction cases | 18 | 18 | 0 | Entire suite passed serially at 360×800 and 390×844 |
| Native Android unit | 5 | 5 | 0 | Fresh Gradle unit execution; routing and local-server address handling |
| **Total** | **649** | **647** | **2** | Distinct cases, not assertion or HTTP-request counts |

Production frontend build, Android debug APK build, and isolated-site migration
completed successfully. No production deployment or Git push was performed.

## Environment and data protection

- Checkout: `main` at `9688945`, plus the existing uncommitted local implementation
  and the test/documentation additions from this exercise. This is a report on
  that working tree, not proof that the same build is deployed online.
- A fresh backup of `sevamrita.local` was taken first. Tests used a separate restored
  site, `sevamrita-regression-20261027.local`, and database
  `_sevamrita_regression_20261027`, served at `http://127.0.0.1:8002`.
- Original demo records and production data were not changed by these tests.
  The copy contains intentional QA users, projects and real accounting documents
  generated through the tested workflows. Do not use this database as live books.
- Email delivery/sync and the scheduler were disabled on the copy; no background
  worker was started. Password-reset tests exercised the server endpoint and UI,
  not delivery to a real mailbox.
- Installed Frappe: version 16.33.1, commit `988e54f`; its source checkout was clean.
  Database: local MariaDB 11.8. Production versions were not inspected in this run.

## Confirmed defects

### P1 — concurrent login for one employee can return HTTP 500

**Reproduction:** make two independent browser/API sessions submit valid login
credentials for the same employee at the same time. Ten paired rounds produced
20 attempts: **10 HTTP 200 and 10 HTTP 500**, with one failed login in every pair.
This was reproduced independently of the other running suites.

**Observed cause:** Frappe's session metadata update in `frappe/sessions.py`,
`update_user_metadata`, encounters MariaDB error 1020, “Record has changed since
last read in table 'tabuser'.” While handling the resulting QueryDeadlockError,
rollback then raises error 1305, “SAVEPOINT … does not exist.” The failing update
belongs to the installed framework's login/session handling. The custom Home
redirect hook does not write the User record.

**Impact:** someone logging in on a phone and a browser together can see a server
error despite using the correct password. Serial logins passed. This local
reproduction does not establish the behavior of a different production stack.

**Fix direction:** correct and verify the framework transaction/deadlock handling
or use a verified compatible Frappe update, then rerun this exact concurrency
case and ordinary login/logout/mobile tests. Do not hide the failure with a test
retry or change MariaDB settings merely to make the suite green.

**Evidence:** `e2e/tests/portal-regression/login-concurrency.spec.ts`,
`test-results/portal-regression-concurrency-results.json`, its HTML report and
the `parallel-login-statuses` attachment; traceback in `tmp/regression-server.log`.

### P2 — password reset leaves System Management's User editor stale

**Reproduction:** create a User in System Management; create/link and edit its
Employee in HR Management; reopen the User; successfully send a password reset;
then uncheck Enabled and save without reloading. The save fails with:
“This user changed after you opened it. Refresh and try again.”

**Cause:** `people_management.send_managed_user_password_reset` calls Frappe's
`_reset_password`, which changes the User record's modification timestamp. The
endpoint returns the username only. `SystemManagement.vue`'s `resetPassword`
does not refresh the editor's `modified` value, so its next save supplies the
old timestamp. This happens after the user's own reset action, with no concurrent
administrator edit.

**Passed before the failing step:** user creation and role assignment; Employee
creation, linking, phone edit and persistence; password-reset endpoint and safe
response. Disabling after reset in the same editor remains unverified because
the save is correctly rejected as stale.

**Workaround:** reopen/reload the User after resetting its password.

**Fix direction:** refresh the managed User/editor version after a successful
password reset, handling any unsaved edits explicitly. Keep the actual protection
against conflicting administrator edits. Rerun the complete management lifecycle.

**Evidence:** `e2e/tests/portal-regression/management.spec.ts`,
`test-results/portal-regression-followup-results.json`, failure screenshot/context
and trace in the corresponding follow-up HTML report.

Neither application defect was patched or skipped during this test-only task.

## Feature coverage

| Area | Verified coverage |
| --- | --- |
| Home and access | Role menus and authorized action parity for employee, project/accounts/HR managers, Administrator, manager/director/chair, unpaid staff and coordinator; active projects first; search; forced light theme; own profile and bank masking; logout success and injected logout failure; Guest denial of protected APIs |
| Projects | Incomplete planning draft and automatic attachment save; private evidence; submission without changing effective project; assigned manager edits/approval; subsequent changes remain pending; approved/own/review views; basic-member claims without financial disclosure; viewer read-only access and unrelated-user denial; account mapping; budget/commitment calculations and controls |
| Advances | Draft/edit/private quotation; multiple requests and amounts above former employee-grade caps; immediate-manager routing; dynamic hierarchy/outstanding controls in backend; manager decision; employee/project/bank eligibility; subordinate freeze/unfreeze and scope denial; Accounts disbursement; partial/full unused returns and ledger effects |
| Invoices | GST/non-GST PDF and Word generation; optional reference fields, supplier bank data and omitted empty remittance; vendor-address reuse; required/reusable volunteer signature and optional vendor signature; signature invalidation after editing; office-address access |
| Combined invoice and claim | A real signed invoice generated and attached privately without download controls; changing ₹75 to ₹80 invalidates the signature; signing again allows submission; private PDF fetch succeeds; reviewer returns it; employee corrects description/replaces evidence/resubmits; reviewer verifies and it reaches manager approval |
| Expense claims | Normal upload and history; multiple invoice dates split into separately dated claims sharing a submission ID; same-date/invoice/accounting-period rules; receipt correction/resubmission; independent verification; manager approval and backend escalation/partial sanction rules; Accounts classification/splits before posting; reimbursement through Payment Entry to Paid; bank/reference permissions and manager/own-advance paths in backend |
| Purchasing | Separate personal, approval and Accounts perspectives, including combined roles; real request ₹1,800 → assigned manager → supplier advance ₹600 → delivery → full supplier bill → ₹600 advance application → remaining payment ₹1,200 → zero outstanding; private bill; exactly two payments; inclusive-tax reference breakup; excess tax, unauthorized access, quantity/payment ceilings and duplicate protection |
| Donations | General/CSR first choice and different required fields; matching ledger paths; repeat donors; general signed private receipt; CSR accounting without receipt/signature; donation accounting/API permission and validation tests |
| Chart, opening balances and ledgers | Chart tree/detail and Accounts access; create/disable/remove unused account; backend rename/protection rules; actual opening Journal Entry with private proof; duplicate prevention; dated ledger entry/totals; pagination and running balances; cancelled/future exclusion; invalid date/page/foreign-account denial |
| HR and System | User and Employee creation/link/edit/role boundaries; reset endpoint; identified stale-editor failure; fiscal-year creation/reactivation without closing other active years; HR attendance/leave/work-log/payroll exclusion rules through full backend suite |
| Other app backend | Legacy-data cutoff and direct-access controls; Section 8/account/fiscal setup/migration behavior; volunteering/events/participation/ratings; donation and De-addiction Pledge APIs, invalid inputs and API-key checks; mobile session rules |

The expense approval limits page, invoice signature panel, user management and
other long forms are also included in the mobile route/step audit. Route audits
check horizontal overflow, clipped controls, input font sizes and small primary
targets; they are more than page-load checks.

## Tests added and harness maintenance

Added live Home tests for management, fiscal years, Guest denial, role coverage,
search, opening proof and ledger posting, a complete purchase/payment lifecycle,
concurrent login, and the combined signed-invoice/correction lifecycle. Added two
backend ledger regressions for pagination and validation; extended mobile coverage
to all three purchasing pages and fiscal years. Added reproducible JSON/HTML
report destinations and frontend/purchasing test scripts.

Initial new-test failures caused by selectors were corrected against the current
UI: exact accessible form labels, explicit search-option selection and reopening
a claim after a review action returns to its queue. An attempted account-rename
test encountered ERPNext's legitimate five-minute quiet window after GL writes;
that safeguard was retained. Unused-account disable/delete is tested in the live
UI, while rename behavior is tested by the backend module.

The new PDF fixture was also validated as a readable one-page PDF with `pdfinfo`
and `pdftotext`; its purchasing, opening-proof and correction cases were rerun
after that fixture correction.

The first overlapping desktop/mobile execution had two mobile login-related
failures. The complete mobile suite was then run alone and all 18 passed; the
separate paired-login test preserves and reproduces the underlying concurrency
failure. The management and login defects remain failing tests.

## Evidence and reproduction

Instructions: [portal-regression-tests.md](portal-regression-tests.md).

| Evidence | Location |
| --- | --- |
| Backend unit / integration | `tmp/full-regression-backend-unit.log`, `tmp/full-regression-backend-integration.log` |
| Additional ledger module | `tmp/full-regression-ledger-additions.log` |
| Frontend / purchasing fixture tests | `tmp/regression-frontend-unit.log`, `tmp/full-regression-purchasing-fixtures.log` |
| Full desktop run | `test-results/portal-regression-final-results.json`, `test-results/portal-regression-final-report/index.html` |
| Targeted follow-up / final combined flow | `test-results/portal-regression-followup-results.json`, `test-results/portal-regression-combined-final-results.json`, `test-results/portal-regression-final-fixtures-results.json` and their HTML reports |
| Login concurrency | `test-results/portal-regression-concurrency-results.json`, `test-results/portal-regression-concurrency-report/index.html` |
| Latest unique desktop summary | `test-results/portal-regression-summary.json`; generated by `node tmp/aggregate_portal_regression.cjs` |
| Mobile final serial run | `tmp/full-regression-mobile-serial.log`, `test-results/mobile-results.json`, screenshots in `test-results/mobile-serial/` |
| Android fresh unit run / build | `tmp/regression-android-unit-fresh.log`, `tmp/regression-android.log`; JUnit XML in `android/app/build/test-results/testDebugUnitTest/` |
| Frontend production build | `tmp/full-regression-build.log` |

Original failing reports and traces are retained alongside the corrected-run
reports. They are local evidence and excluded from Git by `test-results/` rules.
Test setup utilities under `tmp/` contain isolated-test credentials and must not
be committed with application source. Recreate a fresh isolated copy to repeat
the entire write-heavy suite; do not run it on production or a valuable demo DB.

## Limits and release recommendation

- No legacy Desk-only browser suite was run, following the earlier decision to
  focus browser regression on Home. The complete app backend suite still ran.
- Mobile checks used responsive Chrome viewports. Physical Android/iOS devices,
  Safari/WebKit, native Android instrumented UI journeys and signing/installing a
  release APK were not part of this run. Android unit/build success is not native
  app feature parity or complete device E2E certification.
- SMTP inbox delivery, real bank transfers, Cashfree/Interakt delivery, external
  service availability and production hosting were not verified locally. Controlled
  mocks/fault injection are identified separately from actual database workflows.
- This is regression and workflow testing, not a security penetration audit or
  broad load/soak test. The paired login check is a focused concurrency regression.

**Recommended next action:** fix the two defects, rerun their exact regressions
and affected authentication/management/mobile tests, then rerun the complete Home
desktop gate before treating the result as release-ready. No deploy is authorized
by this report.
