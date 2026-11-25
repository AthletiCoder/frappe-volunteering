# SF Tasks PWA — review and test report

Date: 9 November 2026

## Result

A separate SF Tasks PWA is implemented at `/sf-tasks/`. It uses the ERP database and existing collaboration permissions. The Android apps and existing ERP Home frontend were not changed. Nothing has been committed, pushed or deployed for this PWA.

Local review: <http://127.0.0.1:8002/sf-tasks/>

This local server uses the isolated `sevamrita-regression-20261027.local` database, not production. Local demo login: `demo.chat.ravi@sevamrita.local`, password `DemoChat!2026`.

## Automated checks

All **170 unit/integration checks passed**:

| Suite | Passed |
| --- | ---: |
| PWA model, encrypted offline storage, Outbox, service worker and startup | 38 |
| PWA backend, permissions and Web Push | 17 |
| Existing collaboration workflow | 78 |
| Existing collaboration channel access | 8 |
| Existing native push | 18 |
| Existing ERP frontend navigation | 11 |

The production asset build, source compilation and `git diff --check` passed. The pre-existing `volunteering/public/node_modules` symlink modification was left untouched.

Seven additional end-to-end **HTTP workflow groups** passed against the isolated local site:

1. Separate install identity, public app shell and limited worker scope.
2. Workspace creation and membership.
3. Idempotent messages, private attachments, mentions, edits and read receipts.
4. Viewer write denial.
5. Task In progress, assigned subtasks, deadlines and completion validation.
6. Multi-person status tracker, old/current progress, comments, files and history.
7. Events, calendar, nested lists and search.

These are API workflows, not seven additional browser test suites. Their temporary test workspace was archived after each run.

## Interactive browser checks

Checked the real local PWA through the browser at desktop and mobile widths, including 390 × 844 and 320 × 740:

- Login, chat navigation and mobile layout; no horizontal page overflow at the checked widths.
- Full-page tracker creation, stage responsibility, workflow progress and comments.
- Full-page task creation, assigned subtasks, In progress and subtask completion.
- Private file access and saving a file for offline use.
- Light and dark appearance.
- PWA update prompts and activation; verified the page loaded the newly built asset.
- Stopped the server, reopened saved content, restored a message draft, queued the message offline and reloaded it successfully.
- Restarted the server and retried the Outbox. It emptied, with exactly **one** matching message in the ERP.
- Fixed and regression-tested a startup race that made an initial cached tracker refresh run before the CSRF session was ready. Repeated tracker deep-link navigation and reload after the fix without the false “Invalid Request” error.
- Reproduced a blank inline PDF preview with a private demo attachment. Replaced the embedded browser viewer with a bundled PDF.js renderer. Verified that both the tracker attachment and the saved copy display the PDF in the browser. The download option remains available.

The latest light-theme screenshot is `tracker-light.jpg` beside this report.

## Implemented coverage

Chats, groups/workspaces, membership, replies, edits/removal, attachments, mentions, read/delivery receipts; tasks/subtasks and recurring/snoozed work; four tracker types with per-stage assignment, sharing, progress snapshots, comments and files; events, lists, calendar, search, mentions inbox; light/dark/system appearance; encrypted account-specific offline data, drafts and durable Outbox; separate install/update identity; browser push and scheduled reminders.

## Android device validation

Android 16 reached the isolated test server through a temporary wireless ADB reverse connection. The device returned HTTP 200 for the app, and Chrome requested the shell, manifest, service worker and cached assets. For this phone test, Chrome uses `http://127.0.0.1:8002/sf-tasks/` on the phone. The debugging connection forwards that address to the laptop. A deployed PWA should use its HTTPS site.

**Installation and live background Web Push passed on Android 16.** Chrome installed the PWA as a WebAPK, the demo account signed in, and the server accepted its push subscription. A message from a second demo account triggered the normal web notification hook. Processing that specific job on the isolated site sent it successfully on the first attempt. Android showed one matching notification under the installed WebAPK while the launcher was in front. The separate native push channel was suppressed for that test transaction to isolate the PWA delivery.

**Notification tap-through passed on the installed PWA after a fix.** Using wireless debugging, reproduced the original behavior where tapping dismissed the alert while the app stayed in the background. The updated service worker foregrounds the existing window before navigating and falls back to opening the target directly. Activated the update on the phone, sent a fresh background notification and tapped it via wireless debugging. The installed app displayed the expected test conversation and the ERP marked the exact message as read. Automated checks cover the existing-window order, a failed focus and a cold launch.

Automated push tests use mocked external transport plus real VAPID signing. The Android test used the real Chrome push service. A deployed site needs its workers and scheduler for automatic delivery. Android PDF rendering and scheduled reminders on the device remain unverified.

Some functionality depends on connectivity: server search, membership changes and sending uploaded files. Background Sync is used where supported; foreground/reconnect retry is the fallback. Storage can be evicted by the browser, and known access revocation is applied after reconnection. See the source `pwa/README.md` for operating and privacy details.
