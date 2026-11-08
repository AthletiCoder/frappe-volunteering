# SF Tasks 0.6.0 validation — 8 November 2026

## Implemented

- Light, Dark and System appearance. The dark palette retains separate pending, active and completed colours; text, icons, bars and date/time pickers follow the theme. Web forced-light behaviour is unchanged.
- Task subtasks: titles, responsible people, deadlines and Open / In progress / Completed status. Parent completion requires completed subtasks. Weekly/daily/monthly recurrence creates fresh open subtasks and shifts their deadlines.
- Tracker Comments: a separate tab for comments and member mentions. Commenting does not change tracker progress. Conversation viewers can read; item-only sharing does not disclose internal comments.
- Chat @mentions from current members and a My mentions inbox with unread filtering and opening the original context.
- Private encrypted drafts and outgoing work, scoped by account and ERP host. Messages, task saves/status, subtasks, progress, tracker files and comments can wait in Outbox. Android retries Waiting work. Validation, access and version conflicts require attention instead of silently overwriting changes. Conversation administration, sharing and message editing/removal still require a connection.
- History search across messages, tasks, trackers and private filenames, including older messages outside the recent chat window.
- Per-account/per-phone chat notification preferences, per-conversation overrides, quiet hours and reminder controls. Chat alerts during quiet hours are suppressed; due task/tracker reminders are deferred and grouped. Android background scheduling still governs retry and alert timing.

## Final automated checks

| Check | Result |
| --- | --- |
| Collaboration backend | 78 passed |
| Web/app role and access boundary tests | 8 passed |
| FCM delivery, mentions and assignment checks | 18 passed |
| Android debug unit tests | 109 passed |
| Android release unit tests | 109 passed |
| Browser collaboration regression (including 360/390 px layouts and native HTTP flows) | 22 passed |
| Home/frontend regression | 11 passed |
| Release preparation tests | 3 passed |
| Android debug/release lint | No errors; 49 warnings per variant, including existing style/deprecation suggestions |
| Signed debug and release builds | Passed; version 0.6.0 / code 23 |
| APK channel, metadata and existing-certificate checks | Passed for both packages |

## Physical Android 16 phone

All checks used SF testing and the isolated `sevamrita-regression-20261027.local` database. No production records were changed.

- Inspected the dark settings, tracker, subtasks and calendar picker. Fixed the header back-arrow contrast and kept all five tracker tabs visible.
- Added a tracker comment through the UI and verified exactly one saved comment.
- Typed an @mention, chose Arjun Sharma, continued typing, and verified that the name and recipient were retained. A cursor-position bug found during this check was fixed and covered by a new test.
- Opened My mentions and navigated back to the referenced message.
- Searched for a task, opened it, changed a subtask to In progress, added a new subtask and saved a deadline through the calendar picker.
- Stopped only the local test server. Confirmed an unsent draft survived process termination and reopening the app. Sent the message while disconnected: it remained in Outbox, then sent automatically after the server returned. The database confirmed one message and the correct mention recipient.
- Rechecked cached offline conversation opening without a connection-error banner. Session and access errors remain explicit.
- Framework instrumentation on the final build passed: AES-GCM disk persistence and attachment retention, account/server isolation, duplicate-safe queueing/replay/removal, and notification preference decisions.
- Removed the temporary instrumentation APK. SF testing 0.6.0 remains installed. Appearance is set to Dark in SF testing.

## Scope and release state

Both signed APKs are prepared in `output/sf-tasks-0.6.0/`. The SF testing build defaults to the laptop's current private Wi-Fi address, `192.168.29.204:8001`; that address remains editable. The production SF Tasks APK connects to ERP production and needs the matching backend/schema update before its new server features can be used there.

The new Collaboration Operation DocType and the Entry/Read State fields were synced and tested only on the isolated local site. A normal ERP `bench migrate` must sync those schemas when a separately authorised deployment is performed. Existing chats/tasks/trackers are retained. This report records local validation before the source push. No production deployment, app release publication or update-feed replacement was performed for 0.6.0.

Browser fixtures created by the regression runs and the temporary phone feature workspace were archived after testing. Prior user/demo workspaces were retained. The temporary port 8002 server was stopped; the isolated local phone test server remains on port 8001.
