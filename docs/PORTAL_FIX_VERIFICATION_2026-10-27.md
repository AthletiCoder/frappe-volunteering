# Login and password-reset fixes — 27 October 2026

Both defects from the initial portal regression report have been fixed locally.
**Final verification: 654 distinct tests passed; no failures.** This includes
the complete 70-case live Home E2E run, without skipped or flaky cases.
This follow-up records the implementation and verification; the original report
remains the evidence of the failures before correction. Nothing was pushed or
deployed, and the production database and original demo database were untouched.

## Changes

### Concurrent login

The app installs a narrow compatibility wrapper around Frappe v16's
`sessions.update_user_metadata`, using supported `on_login` and `before_request`
hooks. The installed Frappe source is unchanged.

Frappe still authenticates the password, checks account/IP/hour/2FA restrictions,
creates the session, applies session limits and handles authorization normally.
Only its best-effort `last_login`, `last_ip`, `last_active` update and associated
notifications run using a separate database connection. That connection is
committed/rolled back and closed independently, then the request's database is
restored. No business transaction is committed or rolled back by the wrapper.

A nonblocking User-row lock prevents the second connection from waiting on a
User edit held by the login's own transaction. If that row is busy or metadata
fails, activity refresh is skipped and logged; the next activity update can
refresh it. Authentication errors are outside this handler and remain errors.
Installation is idempotent; other sites without this app and SQLite retain the
original helper. If the framework no longer provides the helper, the hook does
nothing. No database schema or global isolation-setting change is needed.

Source: `volunteering/volunteering/login_session.py`, `volunteering/hooks.py`.

### Password reset followed by editing

The reset endpoint accepts the editor's expected modification timestamp, reads
and locks the User, rejects a stale editor before resetting, and returns the new
timestamp without exposing the reset link or key. Older clients may continue to
call the endpoint without the new optional argument.

The Home editor adopts only that new timestamp. It preserves unsaved names,
roles and other inputs instead of reloading over them. It does not update a
different or reopened editor when an earlier request completes. Save and reset
are mutually disabled while either operation runs. Genuine conflicting edits
remain protected by the existing version check.

Source: `frontend/src/views/SystemManagement.vue`,
`volunteering/volunteering/people_management.py`, plus regenerated frontend assets.

## Verification

All writes use the isolated `sevamrita-regression-20261027.local` copy at port
8002, with email delivery/sync, workers and scheduler disabled.

| Check | Result |
| --- | --- |
| Complete backend unit suite | 152 passed |
| Complete backend integration suite | 383 passed |
| Frontend unit tests | 9 passed |
| Purchasing browser fixture suite | 22 passed |
| Production frontend build | Passed |
| Complete live Home E2E suite | 70 passed, no skipped/flaky/retried cases |
| Mobile route/layout suite | 18 passed at 360px and 390px |

New backend tests cover idempotent installation, Guest/no-op handling, separate
commit and connection restoration, deadlock/lost-savepoint handling, connection
cleanup failure, a busy User, an actual User-row lock in the caller's transaction,
the refreshed password-reset version and rejection of a stale reset request.

The live concurrency case makes ten simultaneous two-device login pairs. It
checks all 20 responses, both authenticated identities, and that `last_login`
actually changed. A separate negative test checks that a wrong password remains
rejected and cannot access the authenticated identity endpoint.

The management case creates a User, links/edits its Employee, makes an unsaved
name edit, resets the password, verifies the pending name remains, disables and
saves the User, and checks the stored name and disabled state.

## Local evidence

- `tmp/fix-full-backend-unit.log` and `tmp/fix-full-backend-integration.log`
- `tmp/fix-session-tests.log` for focused transaction checks
- `tmp/fix-people-final.log` for the final nine management tests
- `tmp/fix-frontend-unit.log`, `tmp/fix-purchasing-ui-final.log`
- `tmp/fix-frontend-build.log`
- `test-results/fix-full-portal-results.json` and
  `test-results/fix-full-portal-report/index.html`
- `tmp/fix-mobile.log`, `test-results/mobile-results.json` and screenshots in
  `test-results/fix-mobile/`
- The original failing reports/traces remain under their original report names.

The initial row-lock-only experiment still reproduced the login failure and was
replaced before final verification. An early mocked password-reset assertion was
corrected to compare the newly returned timestamp as a string. These failures
are retained in the local logs; no functional failure was skipped or retried to
claim a pass.

Physical-device/native Android E2E, SMTP inbox delivery, live bank/provider calls
and production hosting are not tested by this local follow-up. Legacy Desk-only
browser tests remain outside the agreed Home scope. The earlier Android build
and five unit passes are unchanged evidence; they were not rerun for these web
and backend fixes.
