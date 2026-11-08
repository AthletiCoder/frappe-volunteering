# Activate chat push notifications

The code supports native Android message alerts using Firebase Cloud Messaging (FCM). It does not need Firebase Hosting, Firestore, Analytics, paid Cloud Functions or a Google Play listing. Register the Android apps in Firebase even though their APKs are distributed directly.

The Firebase project `sevamrita-sf-tasks` and both Android app registrations were configured on 8 November 2026. The isolated local regression site has private sender credentials; live Google OAuth authentication succeeded and the FCM validation endpoint rejected an intentionally invalid device token as expected. Real FCM delivery, notification navigation, foreground suppression, duplicate handling, sign-out cleanup and normal process restart were subsequently verified on the paired Android 16 phone using SF testing. The final APK also fixes and verifies clearing alerts when their chat is opened directly. Production has not been configured or deployed as part of this setup. See [FIREBASE_VERIFICATION_2026-11-08.md](FIREBASE_VERIFICATION_2026-11-08.md). Sites without configuration keep chat and local task/tracker reminders working with push disabled.

## One-time project setup

1. Open the [Firebase Console](https://console.firebase.google.com/) with Sevamrita's organisation Google account. Create a project such as **Sevamrita SF Tasks**; Analytics is optional and is not needed by this app.
2. Add an Android app with package **`org.sevamrita.mobile`**. Download its `google-services.json` and rename the local copy `sf-tasks-google-services.json`.
3. Optionally add **`org.sevamrita.mobile.local`** as a second Android app in the same project for SF testing. Download and rename that config `sf-testing-google-services.json`. Local testing and production retain independent ERP sessions, packages, registrations and update feeds.
4. Enable **Firebase Cloud Messaging API (HTTP v1)** if necessary. Use a dedicated service account with a custom project role containing only `cloudmessaging.messages.create`; Google's built-in FCM API Admin role also includes topic subscription management and read permissions. Generate a private service-account key, or generate a 2048-bit RSA private key locally and register its self-signed X.509 public certificate through Google Cloud. Keep the private JSON credential private; never add it to Git, release assets, email, chat messages or a public files folder. Locally generated uploaded keys expire with their certificate; replace the current sender key before 8 November 2027.

## Configure an ERP site after its separately approved deployment

Deploy the app code and run its normal site migration first; it creates the two private device/outbox tables and installs the retry scheduler. Upload the service-account JSON and the Android config JSON files to a restricted directory **inside that site's `private/` directory**. The CLI helper validates matching project IDs, packages and the signing-key format, writes the Firebase values to private `site_config.json`, and returns only the project/packages. It does not print credentials.

Run from the bench directory, substituting the actual site and absolute private file paths:

```sh
bench --site YOUR_SITE execute volunteering.volunteering.collaboration_push_setup.configure --kwargs '{"service_account_file":"/absolute/site/private/firebase-service-account.json","tasks_config_file":"/absolute/site/private/sf-tasks-google-services.json"}'
```

For the separate local test site, include `testing_config_file` pointing to its private `sf-testing-google-services.json`. A site may configure only the package it needs. The helper is not a web API. Keep the background workers and scheduler enabled, then reload workers after configuration. For Frappe Cloud, use its site console/private-file support; do not publish secrets in the application repository. Disable sending by setting `sf_tasks_firebase.enabled` to false in private site configuration.

The native app fetches the public Firebase project/app settings after ERP login during background sync. There is no need to embed the private service account in an APK, or rebuild an APK just to activate a site's Firebase configuration. Existing 0.5.0 installs need the new 0.5.1 APK through their in-app update flow once that release is published.

## Acceptance check

- Install the matching new APK on two phones with Google Play services. Log in with two enabled **App chat access** users in the same conversation and allow Android notifications.
- Allow one background sync after login so the devices register. Send from A with B's app in the background. B should receive a notification that opens the correct conversation. A should not be notified about A's own message.
- Repeat with B's app process stopped normally (not Android's Force stop), with the conversation actively open, after marking the message read, after removing B from the chat, after revoking B's App chat access, and after B signs out/switches accounts. Old-session notifications must not expose messages.
- Offline phones receive eligible queued delivery after reconnection. FCM wake-ups expire after 24 hours. Android notification permission, device battery policies and a valid ERP session are required; Android Force stop blocks reception until the user opens the app again.
- Check that invalid/uninstalled-device tokens are disabled, transient delivery failures retry, and a duplicate wake-up does not create duplicate alerts. The server stores no message content in the push payload: only an entry ID and session binding go through FCM; the receiving app fetches message text from ERP after rechecking access.

Scheduled task/tracker reminders use the existing local alarms. Simultaneous due tasks now become **one summary**, with distinct tasks listed inside it, instead of one notification per event. Opening a new build clears old per-task reminder cards and cancels the old individual alarms. Multiple real tasks with identical titles remain distinct tasks; the summary displays the actual count.

Reference: [FCM Android client setup](https://firebase.google.com/docs/cloud-messaging/android/get-started), [FCM HTTP v1 server authentication](https://firebase.google.com/docs/cloud-messaging/send/v1-api).
