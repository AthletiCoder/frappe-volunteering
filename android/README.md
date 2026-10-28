# Sevamrita Android

Native Kotlin/Jetpack Compose client for Sevamrita's role-aware Home services. It has no `WebView`, browser bridge, Desk route, or embedded website. The existing website and its assets are unchanged by this Android project.

## Build

Open this `android/` directory in Android Studio and build the `app` module, or run:

```sh
./gradlew :app:assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Android 8.0 (API 26) or newer is required. Debug builds can connect to a local bench on an emulator (`10.0.2.2:8001`) or a phone on the same Wi-Fi using the laptop's private IPv4 address. Release builds allow only the fixed HTTPS Production host.

The generated release APK is **unsigned**. Do not distribute it until you configure Sevamrita's signing key and complete on-device testing. The debug APK is for internal testing only.
Debug builds default to Local Wi-Fi / emulator. Choose Production on the sign-in screen only when you intentionally want to use live data. Local HTTP is debug-only and should be used on a trusted private network: credentials and session traffic are not TLS-protected there.

For a physical phone, keep the laptop's local Frappe server listening on port 8001, put phone and laptop on the same non-isolated Wi-Fi, and enter the laptop's Wi-Fi IPv4 address (for example `192.168.0.5`, without `http://` or a port) on the app sign-in screen. Test `http://<laptop-ip>:8001/api/method/ping` in the phone browser first. Allow inbound TCP 8001 in the laptop firewall if necessary. The app talks to the Frappe API; the phone never connects directly to MariaDB. If the laptop IP changes, update the sign-in field.

The app asks for the same username and password as the portal. It stores only Frappe's session cookie, encrypted with an Android Keystore key, and retrieves a same-session CSRF token from `volunteering.volunteering.mobile_session.get_mobile_session`. This endpoint must be deployed on the selected server before the app can sign in there. No API key or elevated permission is created. Logging out deletes the local session.

## Native coverage in this build

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

Before distributing beyond internal testing, exercise each role and permission path on a physical Android device against the local bench, including private receipts, signature invalidation, account posting, and file-picker flows. This workspace had no connected Android device/emulator for a visual run; only compilation, Android unit tests, API reachability, and APK signature were verified here. The backend `mobile_session` endpoint must be deployed on any remote server selected in the app.
