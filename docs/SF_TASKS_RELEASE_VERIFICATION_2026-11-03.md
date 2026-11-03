# SF Tasks and SF testing — release verification

Verified locally on 3 November 2026. Production deployment is a separate action.

## Scope

- Private chat/workspaces, messages and attachments, tasks, events, lists, progress trackers, per-stage responsibility, individual sharing and scheduled Android reminders.
- SF Tasks 0.4.1: signed production client, normal ERP credentials, production HTTPS endpoint, no demo selector or credentials.
- SF testing 0.4.1: separate local package, demo/manual login, matching post-login interface, editable laptop address.
- Independent Web chat access and App chat access roles. Existing combined-role grants migrate to app access only, preserving membership and content. Users without web access retain normal ERP Home sections.
- Permission-aware caches and quiet refresh, current-stage milestone bars, navigation/draft retention and native attachment previews.
- Newer main commits adding pledge city/image updates were incorporated before verification. Guest pledge-key tests now run as Guest; the intentional administrator bypass has its own test. Body-supplied pledge keys are excluded from saved raw audit payloads.

## Checks

| Check | Result |
| --- | --- |
| Isolated database migration rehearsal | Passed |
| Backend unit/integration cases, deduplicated across the complete runs and affected reruns | 602 passed; no unresolved failures |
| Home workflow browser regression | 70 cases verified across the full run and targeted follow-up |
| Collaboration desktop/phone browser scenarios | 17 passed |
| Whole-portal mobile layout audit at 360px and 390px | 18 passed |
| Purchasing UI/validation/phone scenarios | 22 passed |
| Frontend JavaScript unit checks | 11 passed |
| Android JVM tests | 72 passed in debug and 72 passed in release |
| Android lint | Zero errors in debug and release |
| Web production build and both Android APK builds | Passed |
| APK signatures, names/package separation and production demo-credential exclusion | Passed |
| Staged Python/JSON syntax and whitespace checks | Passed |

The Home suite includes project proposals/approval/change requests and viewing permissions; expenses with existing or generated signed invoices; private receipts and correction/resubmission; approval, account classification and settlement; multiple dated invoices; advances and returns; bank-account approval; vendor addresses; donations; opening balances and ledgers; purchasing; HR/System management; fiscal years; profile/logout; and role-aware Home navigation.

## Findings and reruns

The first complete backend integration run had one failing newly pulled pledge test: it expected an invalid external key to be rejected while executing as Administrator, which the updated API intentionally exempts. The public API tests now run as Guest; an explicit administrator-bypass test and a no-secret-in-audit-payload test pass. All 14 pledge module tests and all eight chat-access/migration tests passed on the affected reruns. Case-level results from the complete and affected runs were deduplicated to verify that no failures remained unresolved.

The first 70-case Home browser run passed 68 checks and had two 15-second Administrator-login timeouts. The corresponding requests later returned HTTP 200. The office-address test and both login-concurrency/security tests passed on an explicit targeted rerun with the original assertions and timeouts, without automatic retries. The concurrency scenario verified all 20 employee sign-ins. Original failure reports were retained; no timeout was increased to obtain a pass.

Fresh DocType imports can auto-create referenced roles with Desk access enabled. The migration now normalizes both chat roles to have no Desk access. A regression test covers this, alongside disabled-role isolation and idempotent legacy-role migration. Native global-role revocation clears cached login, while denial of one individual chat does not invalidate unrelated conversations. Attachment responses completed for an old session are rejected.

All browser writes ran against the disposable regression database on localhost:8002. Full portal/mobile/collaboration configurations reject the review server on port 8001. Outgoing email and workers/scheduler remained disabled on the clone. Demo content on the review database was not reset by the release tests.

## Practical limits and rollout

This is a local verification, not a production deployment. The backend endpoints and migrations must be deployed before SF Tasks 0.4.x can sign in remotely, and users need App chat access. Web chat needs its separate role. Administrator does not implicitly receive chat access.

An older APK titled Sevamrita still calls the old web API and can therefore show “Web chat access role is required.” Upgrade to SF testing 0.4.x; granting web access to work around the old client defeats the intended separation.

The chat/task/tracker UI and scheduled-notification opening were tested on a physical Android 16 phone in 0.3.9. The 0.4.x APKs were checked by unit tests, builds, lint, artifact inspection and API access tests; the phone's wireless debugging connection was unavailable for a fresh physical-device run. Browser phone-layout tests are not native-device testing.

No real bank transfers, external Interakt/Cashfree delivery, SMTP delivery or Google Play distribution was tested. In-app updates poll approximately every 15 seconds; saves require a server connection. Private saved screens support offline reads, not offline write queuing. Native reminders depend on permissions, Android power policies and periodic schedule sync.

APKs and detailed test logs remain under the ignored local output directory. Signing keys/configuration and local node_modules links are excluded from Git. Keep secure backups of the private release signing files for future updates.
