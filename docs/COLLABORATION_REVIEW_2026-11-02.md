# Chat and workspaces: local review

The new collaboration module uses the existing ERP database and session login. Web Home and the native Compose Android screens call the same permission-checked services. Production has not been changed.

## Try it

Open `http://127.0.0.1:8001/volunteering/home` on the laptop. The Android local-testing build uses `http://192.168.0.5:8001`; keep the laptop running and connect the phone to the same Wi-Fi. The login screen lets you change the private IP address if the laptop's address changes.

These fictional accounts exist only in the local development database:

| Login | Name | Kitchen workspace access |
| --- | --- | --- |
| demo.chat.ravi@sevamrita.local | Ravi Menon | Owner |
| demo.chat.arjun@sevamrita.local | Arjun Sharma | Member |
| demo.chat.dev@sevamrita.local | Dev Patil | Viewer |

Password for all three: `DemoChat!2026`.

APK version `0.3.1-local` adds a demo-user dropdown: select Ravi, Arjun or Dev and tap **Sign in** without typing a password. Log out first if an earlier installation has an active session. Manual login remains available for other accounts. This convenience is limited to the local-only debug APK; release builds contain no demo credentials.

Go to **Collaboration → Chat & workspaces**. In Android, open **Collaboration** from Home's Explore section.

The **Pune Community Kitchen** workspace includes a **Weekend meal service** subarea, a linked procurement task assigned to Arjun, a nested kitchen checklist, a weighted stage tracker, a planning event, messages from Ravi and Arjun, and a readable demo PDF. Ravi and Arjun also have a direct conversation.

1. As Ravi, open the kitchen workspace, manage members, create a subarea, send a message or attach a file. Use a message's actions to create linked work.
2. As Arjun, reply, complete the assigned task, update the shared checklist and record tracker progress with a note.
3. As Dev, check that the conversation, work items and PDF can be read, while contribution and management controls are unavailable.
4. Open **My collaboration work** to see assigned work, due/overdue actions and calendar items.
5. With a System Manager account, use **System management → Users** to select **Chat access** for another account. Removing that role blocks the collaboration services and private file access.

## Access and behaviour

- **Chat access** must be assigned explicitly. Other roles, including Administrator's implicit permissions, do not automatically enrol users in chat.
- Direct messages are restricted to their two participants. Groups and workspaces have Owner, Manager, Member and Viewer access. Nested areas inherit root workspace membership.
- Owners manage membership and archiving. Managers can organise work and manage Member/Viewer membership, but cannot promote themselves or change Owners/Managers. Members can contribute; Viewers can read.
- Conversation membership does not grant project financial visibility or approval authority. Project links remain optional.
- Messages support replies, notes, decisions, blockers, milestones and private attachments. Removed messages become tombstones; linked work remains.
- Tasks support assignees, importance, action windows, optional deadlines, recurring occurrences, completion/failure/reopening, snoozing and postponement. Only contributing members can be assigned work.
- Shared lists support ordered, nested entries and completion. Concurrent stale edits are rejected.
- Trackers support percentage, numeric/unit, weighted stages and custom statuses. Progress notes create dated snapshots in chat; backdated updates preserve newer current progress. Tracker outcomes do not automatically complete tasks.
- Events have start/end times, locations and workspace participants. Dates and times use the portal's local time.
- Home shows live reminders for unread updates and actions needing attention. Open chat screens refresh approximately every 15 seconds. No external email or push-notification service was enabled.
- PDF/image attachments open in the Android viewer. Text attachments have a preview; other document formats can be saved for opening in a compatible app.

## Verification

The regression database was isolated from the review database. Targeted checks passed:

| Checks | Passed |
| --- | ---: |
| Collaboration backend integration | 37 |
| Existing Home, private files, user management and mobile session tests | 45 |
| Frontend JavaScript tests | 10 |
| Desktop and phone browser scenarios (360/390 px) | 12 |
| Android unit tests | 8 |
| Total | 112 |

The web production build and Android debug APK build passed. The APK signature was verified. Login was checked against the local database through both localhost and the laptop's Wi-Fi IP. No physical Android device or emulator was available; installation and device interaction still need your review.

The APK is a signed local-testing debug build, package `org.sevamrita.mobile.local`, version `0.3.0-local`, Android 8 or later. It does not offer production as a server option. Existing ERP web workflows remain available. Nothing has been pushed or deployed.

A local database backup was taken before migration: `20261102_220546-sevamrita_local-database.sql.gz` in the bench site's private backup folder.

## Android review update — 3 November 2026

The 0.3.5-local APK has compact task rows with an In progress status action, readable date ranges/deadlines, full-row tracker navigation, Open-default header filters and a floating creation button. Tracker creation/configuration is full screen. Newly created trackers open directly and Back restores the previous list. Personal tracker filters include closed outcomes without exposing other assignees' records; direct links can load older items outside the initial room list.

Verification: 44 Android unit tests and 41 collaboration integration tests passed; Android lint had no errors, and debug packaging and release Kotlin compilation passed. The signed APK remains local-only and uses the same application ID and debug certificate for upgrading. Local Wi-Fi API authentication/read checks were repeated. No emulator was installed and no physical device interaction was performed; visual/keyboard behaviour needs the user's device review. No push or deployment was performed.

## Assignment, sharing and reminders — 3 November 2026

The 0.3.6-local APK supports whole-tracker or per-stage assignments, individual sharing of tasks/trackers with View or Update permission, and native scheduled notifications. Automatic visibility stays within chat membership; the reporting hierarchy grants no access. Sharing does not expose the conversation or private attachments and can be revoked by the creator or workspace Owner/Manager. Targets must have Chat access. Native status/progress updates are available to shared Update recipients, while settings and resharing remain restricted.

Reminders default to 09:00 in the portal time zone when no time is chosen. The app downloads schedules for Android AlarmManager and refreshes them with JobScheduler. Exact timing and notification permissions have a settings UI. Background schedule updates depend on server/network availability; offline cached schedules may remain until the next successful sync. No email, Firebase push infrastructure, emulator or production deployment was introduced. Actual delivery, reboot recovery and permission interactions still need physical-device review.

Verification passed: 52 backend integration tests, 50 Android JVM tests, 14 browser E2E scenarios including 360/390-pixel layouts, and 10 frontend tests. Android lint reported zero errors; debug packaging, release Kotlin compilation, frontend build and APK signature verification passed. The browser sharing-picker label issue found during these checks was fixed. Role-cache cleanup was added to isolate the role-revocation integration test.

Local demo: Pune Community Kitchen includes Community kitchen service handover, divided between Ravi Menon and Arjun Sharma. Ravi's private Kitchen coordination notes includes Check meal-delivery contact numbers, shared individually with Arjun with Update permission. Arjun can open the task from My tasks but cannot open that private chat. Existing demo credentials and application ID are unchanged. APK: output/Sevamrita-Chat-Local-0.3.6-20261103.apk.

## Login failure and review-data correction — 3 November 2026

The new reminder scheduler used a network constraint without declaring Android 14+'s required ACCESS_NETWORK_STATE permission. A scheduler SecurityException after the UI marked login successful could enter the login failure handler and clear the cookie, leaving a signed-in UI whose next task/tracker request said Please sign in again. Version 0.3.7 adds the normal permission, separates reminder startup from authentication failure, and returns missing-session cases to login. Loading/error chat states no longer render as read-only membership.

Archived exactly 12 test-generated QA kitchen workspaces on the review site, using strict title/creator/membership matching and a recovery snapshot at output/archived-qa-chats-20261103-194400.json. Ravi's own Checking tracker remains; his active chat and tracker editing permissions were verified through the API. Browser tests are now restricted to the separate regression site on localhost:8002, with both port and server-side site-marker checks before any work-item writes. The review-port rejection was verified.

Verification: 54 Android unit tests, 14 browser E2E scenarios on the isolated database, zero Android lint errors, debug APK and release Kotlin compilation, APK signature, and the packaged network permission passed. Native phone interaction still requires device review. APK: output/Sevamrita-Chat-Local-0.3.7-20261103.apk; same local package/certificate as before. Production has not been changed.

## Tracker groups — 3 November 2026

APK 0.3.8-local displays My trackers under chat headings with counts, removes repeated chat names from cards, and preserves filtering and whole-card navigation. Added three requested local demo groups with nine trackers; eight are open and one completed. Both Ravi and Arjun can see the examples and open their trackers with Update access. Existing user content was retained and archived QA fixtures remain hidden.

Targeted verification passed: 59 Android unit tests, zero lint errors, debug packaging and release Kotlin compilation, and local Wi-Fi API checks for both accounts. The APK signature and package version were verified. No browser E2E suite was rerun for this native grouping change, and no production change was made. APK: output/Sevamrita-Chat-Local-0.3.8-20261103.apk.


## SF Tasks and SF testing release review — 3 November 2026

The current apps are SF Tasks (normal ERP email/password login, fixed production HTTPS server) and SF testing (separate local package with demo dropdown and manual login). Both expose chat, tasks and trackers after login. Web chat access and App chat access are independent, server-enforced roles; existing combined Chat access grants migrate to App chat access without enabling collaboration in web Home. System Management → Users can assign either or both. Existing conversation membership and item sharing remain unchanged.

Version 0.4.1 also returns a revoked global app role to login with a clear access message, rejects downloads completed for an old session, and normalizes newly imported chat roles to have no Desk access. The private production signing key and its configuration, APKs, generated reports and temporary scripts remain outside Git. Financial policy documents included in docs/policies are drafts and do not implement accounting-policy changes.

An older app displaying the title Sevamrita still uses the earlier web API. Install SF testing 0.4.x over that local app to use only App chat access; do not grant Web chat access just to accommodate the old APK. A fresh production deployment must include the backend and migrations before SF Tasks can sign in. No deployment is performed by the verification/push work.
