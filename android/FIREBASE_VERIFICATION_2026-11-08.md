# Firebase configuration verification — 8 November 2026

## Completed

- Project: `sevamrita-sf-tasks` (Sevamrita SF Tasks), Spark plan; no billing subscription enabled.
- Cloud Messaging HTTP v1 shows **Enabled** in Firebase Console.
- Registered Android packages: `org.sevamrita.mobile` and `org.sevamrita.mobile.local`.
- Dedicated service account: `sf-tasks-notification-sender@sevamrita-sf-tasks.iam.gserviceaccount.com`.
- Custom project role: `projects/sevamrita-sf-tasks/roles/sfTasksFcmSender` with exactly **one permission**, `cloudmessaging.messages.create`.
- The service account was granted only that custom project role. Google's broader built-in FCM role was not granted.
- A 2048-bit RSA private key was generated locally, and its public X.509 certificate was registered in Google Cloud. The private key was never entered into the browser. The certificate expires on **8 November 2027**; rotate before expiry.
- Public Android configuration and private sender JSON were validated and installed only in the private configuration of `sevamrita-regression-20261027.local`.
- Setup files are in that site's `private/firebase/` directory, with directory permissions 0700 and file permissions 0600. Site configuration permissions are 0600. No secret is included in this repository or the APK.

## Live server checks

- Google OAuth token exchange using the actual sender key and the app's existing `_access_token()` implementation: **passed**.
- FCM HTTP v1 validation-only request using that token: **HTTP 400 / INVALID_ARGUMENT**, explicitly stating the deliberately fake registration token was invalid. No actual phone notification was sent.
- These initial server-only checks were followed by the real phone tests below.

## Real phone checks

Tested on the paired Android 16 phone with **SF testing 0.5.1-local (version code 21)**, the isolated regression database and the real Google FCM service. The receiving account was Ravi Menon; Arjun Sharma sent messages in the local-only `Phone review - Pune Kitchen` chat. No production chats or accounts were changed.

| Check | Result |
| --- | --- |
| Phone fetches runtime Firebase settings and registers an encrypted device token in ERP | Passed |
| Incoming background message displays the correct conversation and sender | Passed |
| Sending the identical FCM wake-up twice does not duplicate or re-alert the message notification | Passed; notification ID and creation/update times stayed unchanged |
| Tapping the actual Android notification opens its conversation | Passed |
| Delivered acknowledgement reaches ERP before opening; seen acknowledgement follows reading | Passed |
| An already-open conversation displays its incoming message without an extra chat alert | Passed, including the final rebuilt APK |
| Incoming FCM message restarts a normally closed background process and displays an alert | Passed; no app process was running before delivery, including the final rebuilt APK |
| Switching user disables the old registration and clears existing chat alerts | Passed |
| A simulated in-flight wake-up for the signed-out session displays no alert | Passed |
| Signing into the demo account again re-enables registration for the new session | Passed |
| Opening an alerted conversation directly from the chat list clears its notification | Initially failed; fixed and retested successfully on the phone |

The read-alert fix serialises conversation visibility and alert removal with notification creation, so an incoming push cannot recreate an alert while that conversation is visible. The existing unrelated task reminder was preserved.

The actual app hook generated each outbox record; its normal delivery function was then run explicitly on this isolated bench. A production worker/scheduler deployment smoke check remains necessary. Two-phone delivery, offline/reconnect delivery and extended device idle/battery-policy behaviour were not checked in this session. Android Force stop is not claimed to support background reception.

## Regression checks

The focused `volunteering.volunteering.test_collaboration_push` suite was rerun after local setup: **17 tests passed**. Google delivery is mocked in that suite; the OAuth/API checks above used the real service. A repository scan found no copies of the actual Firebase private key or Android API key in tracked or unignored source files.

The final rebuilt Debug and Release variants each passed **97 unit tests** with no failures or skips. Both lint checks reported **zero errors**. Both signed APKs and their local checksum/update files were refreshed and verified. The corrected SF testing APK was installed on the paired phone; the production SF Tasks installation was not changed.

## Production status

No ERP production deployment or production site credential change was performed. At the end of the phone session the signed 0.5.1 APKs were local; the subsequent release preparation is recorded in [RELEASE_CHECK_2026-11-08.md](RELEASE_CHECK_2026-11-08.md). App publication is separate from backend deployment. Before enabling production, separately obtain deployment approval and run the production worker/scheduler smoke check. Provision the private sender credential through the site's secure administration channel, never by Git push.

## References

- https://docs.cloud.google.com/iam/docs/roles-permissions/firebasecloudmessaging
- https://docs.cloud.google.com/iam/docs/keys-upload
- https://firebase.google.com/docs/cloud-messaging/send/v1-api
