# SF testing phone check — 7 November 2026

Device: A069P / Android 16. App: SF testing 0.5.1-local (version code 21), upgraded in place with the existing signing certificate. SF Tasks production was not installed or changed. All data mutations used the isolated `sevamrita-regression-20261027.local` database served temporarily on port 8001.

Passed on the physical phone:

- Wi-Fi login after changing laptop address; login/settings retained across the final APK upgrade.
- Tracker dashboard counts, attention preview, pending-person highlights and grouping by chat.
- Completed summary/filter shows completed trackers with all milestones marked complete.
- Whole-card tracker navigation, Workflow/Details/Updates/Files tabs, recorded author/progress history, and the Files empty state.
- Take action opens the full-screen progress form. Keyboard leaves Post update visible. Choosing the next stage and saving a note changes responsibility from Ravi Menon to Arjun Sharma and decreases the pending-with-me count.
- Three distinct tasks scheduled for the same minute created exactly one active SF testing notification, titled “3 work reminders”, with three task lines.
- Opening that notification navigates to My tasks. The notification did not reappear after reopening it and restarting/upgrading the app; delivered occurrence tracking was retained.
- Safe system-bar/navigation insets and readable light-theme status icons on the inspected screens.

Refinement after visual inspection: show one attention preview with View all instead of three large previews; combine matching attention/deadline labels on tracker cards. Rebuilt and reinstalled this refinement and checked it on the phone.

Automated verification after the refinement: 97 unit tests passed for each Android build variant, no lint errors, signed release and local APKs built and verified against their existing certificate fingerprints. The preceding server run passed 82 backend tests (17 push, 57 collaboration, 8 interface-access).

Not tested live: Google FCM transport, token refresh or background wake-up, because the Firebase project and site credentials have not been configured. The guide remains `android/FIREBASE_SETUP.md`; mocked delivery/authentication/permission tests are not a substitute for that live acceptance check.

Screenshots and the app-filtered notification record are local test artifacts under `/tmp/sf-phone-20261107/`. Credentials, private messages and other apps’ notification content were not saved in these app-filtered test records. No code was pushed, no app release feed was published, and no production deployment was made during this phone check.

Firebase project and local credential setup were completed on 8 November 2026. See [FIREBASE_VERIFICATION_2026-11-08.md](FIREBASE_VERIFICATION_2026-11-08.md) for the live server authentication check and the phone delivery checks still outstanding.

On 8 November 2026, real Google FCM phone checks passed and a stale chat-alert issue was fixed and physically retested. The corrected SF testing build was installed on the phone. The current results and remaining deployment checks are in [FIREBASE_VERIFICATION_2026-11-08.md](FIREBASE_VERIFICATION_2026-11-08.md).
