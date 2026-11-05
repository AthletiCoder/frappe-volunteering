# SF Tasks and SF testing

## In-app updates (0.5.0 and later)

Install the signed 0.5.0 APK once over the existing app. Later versions appear in a small update banner, or use **Check for updates** from the login screen, Chats menu or a conversation menu. Checks run quietly at most once every six hours on app foregrounding; a manual check is always available. Downloading is optional and shows progress only in the update panel. Android requires the user to allow installation from this app once and confirm each installation. No ERP login or chat state is changed by checking/downloading an update.

The updater uses public GitHub Releases in `AthletiCoder/frappe-volunteering`, independently of ERP deployment. A fixed `sf-tasks-updates` release hosts `sf-tasks-update.json` and `sf-testing-update.json`. Each feed points to an immutable APK on a versioned release such as `sf-tasks-v0.5.0`. Keep the channels separate: production (`org.sevamrita.mobile`) and local testing (`org.sevamrita.mobile.local`) cannot replace one another. The app verifies HTTPS destinations, size, SHA-256, package, increasing version code and the installed signing certificate before offering the APK to Android's installer. Failed/partial downloads are removed and can be retried. Files are shared only through a private, narrowly scoped FileProvider. No ERP credentials are sent to the release host.

To prepare a future release:

1. Increase both `versionCode` and `versionName`, write release notes under `android/releases/`, run the affected tests, and build both signed variants. Preserve the existing release keystore and local debug key.
2. Set `JAVA_HOME` to JDK 17, then run `python3 android/prepare_release.py --tasks android/app/build/outputs/apk/release/app-release.apk --testing android/app/build/outputs/apk/debug/app-debug.apk --notes android/releases/0.5.0.md --output output/sf-tasks-0.5.0` (adjust the version and notes). The helper verifies the APK signatures against public certificate fingerprints, package/version metadata and production debuggability before generating APKs, checksum files and feeds. It never uploads or deploys.
3. Commit and push the matching source to `main`. Use `gh release create sf-tasks-v0.5.0 --target COMMIT_SHA --draft --latest=false --notes-file android/releases/0.5.0.md` and upload the prepared APKs and checksum files to that draft. Download and compare the hosted APK hashes, then publish with `gh release edit sf-tasks-v0.5.0 --draft=false --latest=false`. Never replace an already-published versioned APK; increment the version for a correction.
4. Only after the versioned APKs are published and verified, upload the two new JSON files to `sf-tasks-updates` using `gh release upload sf-tasks-updates output/sf-tasks-0.5.0/sf-tasks-update.json output/sf-tasks-0.5.0/sf-testing-update.json --clobber`. Create that release first if bootstrapping. Before replacement, compare the prior feeds and require a strictly higher version code. Keep the stable release tag: the apps' URLs depend on it. Verify both public feeds and their APK hashes after publication.

APK publication does not deploy the ERP backend. Changes to server APIs still require the separately authorized ERP deployment. Signing keys, passwords, generated APKs and local test data remain outside Git; releases contain only the APKs, checksums and public feed metadata. Automated coverage includes channel separation, URL/redirect restrictions, download size/hash checks, interrupted-download cleanup/retry, package/version/key validation and the installer/provider contract. The Android installer permission/confirmation flow still requires a physical-device acceptance check for a newly shipped updater.

Native Kotlin/Jetpack Compose client for Sevamrita's role-aware Home services. It has no `WebView`, browser bridge, Desk route, or embedded website. The existing website and its assets are unchanged by this Android project.

## Build

Open this `android/` directory in Android Studio and build the `app` module, or run:

```sh
./gradlew :app:assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Android 8.0 (API 26) or newer is required. Debug builds can connect to a local bench on an emulator (`10.0.2.2:8001`) or a phone on the same Wi-Fi using the laptop's private IPv4 address. Release builds allow only the fixed HTTPS Production host.

The production app is **SF Tasks** (`org.sevamrita.mobile`): normal ERP email/password login, fixed HTTPS production ERP server, and no demo account selector or credentials. **SF testing** (`org.sevamrita.mobile.local`) is the separate local debug app. It keeps the demo dropdown plus manual login, editable laptop Wi-Fi address, and the same post-login chat/task/tracker screens. It upgrades the previous local APK in place.

Release signing reads the git-ignored `release-keystore.properties`, which references `signing/sf-tasks-release.jks`. Keep secure backups of both files: future production updates must use the same key. Neither file belongs in Git or in a public artifact. Without that private configuration Gradle produces an unsigned release; verify the signature before delivery. The testing APK uses the existing debug key.
Debug builds default to Local Wi-Fi / emulator. Choose Production on the sign-in screen only when you intentionally want to use live data. Local HTTP is debug-only and should be used on a trusted private network: credentials and session traffic are not TLS-protected there.

For a physical phone, keep the laptop's local Frappe server listening on port 8001, put phone and laptop on the same non-isolated Wi-Fi, and enter the laptop's Wi-Fi IPv4 address (for example `192.168.0.5`, without `http://` or a port) on the app sign-in screen. Test `http://<laptop-ip>:8001/api/method/ping` in the phone browser first. Allow inbound TCP 8001 in the laptop firewall if necessary. The app talks to the Frappe API; the phone never connects directly to MariaDB. If the laptop IP changes, update the sign-in field.

For an APK preconfigured for one laptop and restricted to local testing:

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug -PsevamritaLocalHost=192.168.0.5 -PsevamritaLocalOnly=true
```

This signed debug build installs separately as **SF testing** (`org.sevamrita.mobile.local`), prefills the laptop address and offers no production/staging option. The address remains editable if Wi-Fi assigns the laptop a new IP. The server must explicitly serve `sevamrita.local`, not a regression clone. It embeds no database password or API key. The local-only debug build includes the three fictional chat-demo credentials described below. Omitting the properties keeps normal emulator/debug behavior; release builds remain production-only.

The app asks for the same username and password as the portal. It stores only Frappe's session cookie, encrypted with an Android Keystore key, and retrieves a same-session CSRF token from `volunteering.volunteering.mobile_session.get_mobile_session`. This endpoint must be deployed on the selected server before the app can sign in there. No API key or elevated permission is created. Logging out deletes the local session.

In the local-only debug APK, the default login screen instead offers Ravi Menon, Arjun Sharma and Dev Patil in a dropdown. Selecting one and tapping **Sign in** submits that fixture's existing demo credentials through normal Frappe login; the user need not type a password. **Sign in with another account** retains manual login. Log out to switch demo users. The fixture list and credentials live only in `src/debug`; the release source set provides an empty implementation. The selector is unavailable for production or staging, and backend authentication and role checks are unchanged.

## Access and deployment

- **Web chat access** enables chat, collaboration work and related reminders on the web Home UI.
- **App chat access** enables SF Tasks and SF testing. It does not add collaboration to web Home.
- Give both roles for both interfaces. They share the same ERP records and retain workspace membership and item-sharing rules. App users and web users can participate in the same conversation.
- Administrator/System Manager do not implicitly receive chat access; assign the chosen role explicitly in System management → Users.
- The old combined **Chat access** role is retired. The migration moves existing grants (including role-profile entries) to App chat access and does not automatically grant web access. Existing chats/tasks/trackers remain unchanged.

Native requests use explicit `collaboration_mobile` endpoints, with App chat access checked server-side; the web endpoints require Web chat access. A submitted platform field or HTTP header cannot change the role required by an endpoint. Reminders use the app role. The new backend and role migration must be deployed before the 0.4.0 apps can use a remote site. Building an APK does not deploy the ERP backend.

## Current APK scope: chat, tasks and trackers

Version `0.4.1` adds explicit logout when global app access is revoked and rejects stale-session attachment downloads. It also includes the `0.4.0` changes below.

Version `0.4.0` separates and names the production/local apps, adds email/password visibility and a native forgot-password request through ERP's existing rate-limited reset endpoint, and introduces independent web/app chat roles. Production accepts existing ERP credentials only; local demo credentials are excluded from its release source set. The password-reset action sends a request only when explicitly tapped, and depends on the ERP site's outgoing email configuration.

Version `0.3.9-local` adds dotted milestone bars to both stage and status trackers: filled completed dots, a ring for the current position, and hollow upcoming dots. Lists show the current label and step count; detailed timelines retain stage assignees and configured weights. Status bars express configured order without inventing a percentage.

Routine foreground refreshes and chat prefetching no longer use the saving/busy state or display a moving sync bar. Task/tracker mutation responses update visible records immediately after the server confirms them; the remaining reads happen quietly. Drafts and scroll positions survive screen navigation. Private, per-user/per-server AES-GCM snapshots restore chat lists, personal work and up to 25 recently loaded screens across restarts, including reading cached content while disconnected. Logout removes snapshots, and current access checks prune revoked records. Unsaved edits are not queued offline; saves still require server confirmation. Background changes are polled about every 15 seconds while viewing the app, rather than delivered through a realtime socket.

Version `0.3.8-local` groups My trackers by chat, with one heading and filtered count per chat instead of repeating the chat name on every card. Groups use the chat ID, so equally named chats stay separate; tracker order and whole-card opening are retained. Open/All/Completed/Failed filters are applied before grouping, avoiding empty headings. The local demo includes three additional groups (Talegaon School Support, Powai Health Camp, Hyderabad Volunteer Drive), each with three trackers. One completed venue tracker is intentionally hidden by the default Open filter. Ravi owns these groups, Arjun contributes, and Dev retains viewer access. The additive helper `collaboration_demo.add_group_examples` does not reset existing progress or recreate matching examples.

Version `0.3.7-local` fixes a successful-login regression: Android 14+ requires ACCESS_NETWORK_STATE for network-constrained JobScheduler work. This permission is now declared, and reminder startup/refresh errors are non-critical so they cannot clear a successful sign-in. A genuinely missing session returns to login rather than leaving a broken tracker screen. A chat without a loaded access payload shows Loading/Retry instead of incorrectly claiming viewing access. Unit checks cover the missing-permission contract and failed optional startup.

Collaboration browser tests now use `npm run test:e2e:collaboration` with `playwright.collaboration.config.ts`, localhost:8002, and the existing `sevamrita-regression-20261027.local` site. The test suite checks the server's isolated-site marker before creating any fixtures and refuses the review port/database. The general review-site regression config excludes this suite. The 12 previously generated QA workspaces were archived from the review database with an audit snapshot; real user entries were retained.

Version `0.3.6-local` adds a clear One person / Divide by stage assignment choice, with a contributing chat member for every stage. Task/tracker Share controls grant item-only View or Update access to another enabled Chat access user; creators and workspace Owners/Managers control sharing and revocation. Reporting hierarchy grants no automatic visibility. Shared work appears in My tasks / My trackers without exposing its chat or private attachments. Tracker creators also see trackers they assigned to others.

Tasks and trackers accept an optional reminder time. Date-only schedules use 09:00 in the portal's time zone; action/attention ranges remind each scheduled day, and distinct deadlines also remind. Native AlarmManager notifications survive app closure, and persisted JobScheduler work refreshes schedules approximately every 15 minutes when the server is reachable. Divided trackers remind the creator and the current stage's responsible person (the first stage before any stage is selected). Signed-out sessions and revoked-role syncs clear cached alarms; completed, archived and revoked items disappear at the next sync. Exact timing requires Android's precise-alarm permission. Notifications require Android notification permission; settings are exposed from the Chats overflow menu under Reminders. This is local scheduling plus periodic synchronisation, not an FCM push service, so changes made elsewhere while the phone is offline cannot cancel cached reminders until it reconnects. A timed task notification and its tap-to-task navigation were verified on the paired Android 16 phone on 3 November 2026; delivery across other Android versions and device power policies still needs review.

Version `0.3.5-local` uses compact task rows with an inline Open / In progress / Completed / Failed status menu, clearly labelled schedules and deadlines, and an overflow menu for editing, postponing, snoozing and history. Tracker lists have whole-row navigation to a single tracker, a compact header filter (Open by default), and a bottom-right create button in conversations and tracker details. Creation and configuration use a full-screen editor with safe Android/keyboard insets; newly created trackers open directly. My trackers can also show completed/failed records. Back returns to the preceding list with its scroll position retained.

Version `0.3.4-local` adds native progress trackers. Use the timeline icon in a conversation, **Trackers** in its menu, or **My trackers** from the top bar. Long-pressing a message offers **Create tracker** alongside **Create task**. Trackers support percentage, numeric/unit targets, weighted stages and custom statuses; creation/configuration, assignments, attention windows/deadlines, progress notes, explicit Open/Completed/Failed outcomes and dated history are available. Stage/status dropdowns and clickable timelines share the same unsaved selection. Progress snapshots are visible in chat and retain their recorded values when newer progress exists. Viewers can inspect trackers/history; configuration and progress actions follow the backend's workspace permissions. ERP menus remain hidden.

Version `0.3.3-local` adopts the compact chat-list and thread pattern from the Tasks_Blogging reference: circular avatars, latest-message previews, timestamps and unread badges; searchable/filterable conversations; and incoming/outgoing bubbles with date separators. The composer stays fixed above the keyboard. Long-press a message to reply, copy text, create a task, or edit/remove your own message. Linked tasks appear as compact chips. The chat header opens members/settings and conversation tasks. Switch user remains in the overflow menu, and the local demo-user dropdown is retained.

Version `0.3.2-local` opens directly to conversations. It exposes direct/group chats, workspace membership, private attachments, linked tasks and My tasks. ERP Home, Projects, Expenses, Advances, Accounts and Profile menus are absent. Calendar, Lists and Progress are also hidden in this focused APK. Those modules remain in the source and on the web; the Android launcher exposes only the chat/task interface and its attachment viewer.

System Back and the top Back arrow follow the same visited-screen history, including chat/task tabs and personal tasks. The first screen asks before exiting. Screen state is retained when returning from an attachment. Switch user signs out and resets navigation history.

The activity uses edge-to-edge with a light system-bar appearance. Header padding follows Android's reported safe-drawing top and side insets; Scaffold content consumes those insets and handles the keyboard and bottom system navigation area. Login and dialogs also respect safe drawing/keyboard insets. This follows the [Android inset guidance](https://developer.android.com/develop/ui/compose/system/insets-ui); it does not assume a fixed status-bar height or a particular phone model.

## Retained native modules

- Role-aware Home dashboard with active project cards, work items, drafts, and permitted action groups.
- Project catalogue and role-scoped project details, including financial data only when the backend authorizes it. Native project proposals and change requests support drafts, supporting-document upload with Basic/Financial visibility, submission, history, and assigned-manager review/edit/approve/return/reject.
- Own advances: list, detail, and new project-linked request.
- Own expense claims: list, detail/timeline, private receipt viewing, one-bill and multi-invoice submissions, returned-claim correction, and a combined generate-and-submit flow.
- Manager advance approval/rejection/escalation and expense receipt review or approval, including a native private-receipt PDF/image viewer.
- Employee profile and masked approved bank-account summary.
- Standalone GST/non-GST invoice preparation with on-screen volunteer and optional vendor signatures, saved suppliers, and separate PDF/Word exports.
- Accounts: Chart of Accounts, account ledgers and maintenance, project expense-account mapping, claim classification/reimbursement, advance disbursement/return, opening balances, donation registration, expense approval limits, bank-account review, and budget health.
- Other role-scoped Home features: bank-account submission, office addresses, team/advance freeze, fiscal years, HR employee management, and System user management/password-reset requests.

All authorization and validation remain in the existing Frappe services. Unsupported Home actions show a native explanation and cannot fall through to Desk or a browser. Actions whose Home URL points directly to `/desk/` are hidden from this app.

## Remaining parity and testing gaps

Desk-backed time/leave actions (daily work logs, work-from-home, leave, attendance fixes) are not native yet. Some administrative/volunteering reports and non-PDF/image supporting-document previews also remain on the web/Desk side. They are **not** silently replaced with a web rendering: direct Desk actions are hidden, and unsupported Home routes show a native explanation. This APK is an internal test build, not yet complete feature parity or production-ready.

Before distributing beyond internal testing, exercise each role and permission path on a physical Android device against the local bench, including private receipts, signature invalidation, account posting, and file-picker flows. The chat/task/tracker build was visually tested on the paired Android 16 phone on 3 November 2026, including task status updates, tracker progress, quiet incoming updates, draft preservation and cached offline navigation. This does not verify the retained ERP modules on-device. The backend `mobile_session` endpoint must be deployed on any remote server selected in the app.
