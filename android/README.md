# Sevamrita Android

Native Kotlin/Jetpack Compose client for Sevamrita's role-aware Home services. It has no `WebView`, browser bridge, Desk route, or embedded website. The existing website and its assets are unchanged by this Android project.

## Build

Open this `android/` directory in Android Studio and build the `app` module, or run:

```sh
./gradlew :app:assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Android 8.0 (API 26) or newer is required. Debug builds can connect to a local bench on an emulator (`10.0.2.2:8001`); release builds allow only the two fixed HTTPS hosts.

The generated release APK is **unsigned**. Do not distribute it until you configure Sevamrita's signing key and complete on-device testing. The debug APK is for internal testing only.
Debug builds default to Staging to avoid accidental Production writes; the server can be changed on the sign-in screen.

The app asks for the same username and password as the portal. It stores only Frappe's session cookie, encrypted with an Android Keystore key, and retrieves a same-session CSRF token from `volunteering.volunteering.mobile_session.get_mobile_session`. This endpoint must be deployed on the selected server before the app can sign in there. No API key or elevated permission is created. Logging out deletes the local session.

## Native coverage in this build

- Role-aware Home dashboard with active project cards, work items, drafts, and permitted action groups.
- Project catalogue and role-scoped project details, including financial data only when the backend authorizes it. Native project proposals support new drafts, submission, history, and assigned-manager approve/return/reject.
- Own advances: list, detail, and new project-linked request.
- Own expense claims: list, detail/timeline, and a one-bill submission with an Android document picker for private PDF/PNG/JPEG evidence.
- Manager advance approval/rejection/escalation and expense receipt review or approval, including a native private-receipt PDF/image viewer.
- Employee profile and masked approved bank-account summary.

All authorization and validation remain in the existing Frappe services. Unsupported Home actions show a native explanation and cannot fall through to Desk or a browser. Actions whose Home URL points directly to `/desk/` are hidden from this app.

## Not yet native

Project change requests, proposal attachments, generated invoices and on-screen signatures, multi-invoice bundles, returned-claim corrections, bank-account requests, Accounts ledger classification and settlement, donation entry, opening balances, chart administration, HR and system management, and Desk-backed time/leave tasks. These are **not** silently replaced with a web rendering. Do not treat this build as complete Home parity for every role.

Before distributing beyond internal testing, test on an Android device against a staging bench containing the new session endpoint, then exercise each supported role and permission path. This workspace had no connected Android device/emulator for a visual run.
