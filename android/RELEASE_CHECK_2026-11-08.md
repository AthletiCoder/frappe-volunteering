# SF Tasks 0.5.1 release checks — 8 November 2026

The release contains the tracker dashboard/detail redesign, grouped task/tracker reminders, session-bound FCM alerts, and the alert-clearing fix found during physical phone testing. It preserves the separate production and local testing packages and their signing keys.

## Validation

| Check | Result |
| --- | --- |
| Android Debug unit tests | 97 passed, 0 failures/errors/skips |
| Android Release unit tests | 97 passed, 0 failures/errors/skips |
| Debug and Release lint | 0 errors in each variant |
| Backend collaboration regression | 57 passed |
| Backend web/app role isolation | 8 passed |
| Backend notification integration | 17 passed |
| Browser collaboration regression, including 360/390px layouts | 18 passed on the isolated site; rerun for this release |
| Release packaging/signature/channel tests | 3 passed; rerun for this release |
| Signed APK preparation | Both package IDs, versions, certificate pins, hashes and sizes verified |
| Real Google authentication and phone notifications | Passed the cases recorded in FIREBASE_VERIFICATION_2026-11-08.md |

The Android tests/lint were run against the final alert-clearing code immediately before release preparation. The backend suites ran against the same server implementation; no runtime backend change was made after they passed. This release does not require rerunning unrelated Desk-based finance/HR workflows.

Browser tests used localhost:8002 and `sevamrita-regression-20261027.local`. Live push sending was temporarily disabled during the tests, restored afterwards, and only the 11 new `QA kitchen` workspaces created by this run were archived. Existing demonstration work and production data were retained.

## Publication contract

- Version name: **0.5.1**; version code: **21**. The prior public feeds advertised 0.5.0 / code 20.
- Source changes go to `main` before publishing the versioned `sf-tasks-v0.5.1` release.
- Published APKs must be downloaded and checked against their SHA-256 values before the stable `sf-tasks-updates` feeds are replaced.
- Production and testing feeds remain separate. Users with 0.5.0 or later can use the in-app banner or **Check for updates**, download the APK, and confirm installation in Android. Earlier versions need one manual updater-capable APK installation.
- Firebase private keys, site configuration, signing keys, generated assets and demo data are excluded from Git. Public release assets contain only the APKs, checksums and updater metadata.
- This approval covers source push and app update publication. It does **not** deploy ERP production or install the private Firebase credentials there. Production push activation still needs that separate deployment/configuration and its worker/scheduler smoke check.

Live phone checks covered one Android 16 device using SF testing. Two-phone, prolonged offline/reconnect, other Android versions and extended battery-policy tests were not performed in this session. No claim is made for notification delivery after Android Force stop.
