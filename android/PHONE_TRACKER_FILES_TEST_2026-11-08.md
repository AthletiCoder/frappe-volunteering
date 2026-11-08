# Tracker attachments: physical-phone acceptance — 8 November 2026

Device: A069P, Android 16. Installed and tested **SF testing 0.5.2-local / version code 22**, upgraded in place with the existing signing key. The production SF Tasks package was not installed, replaced, or operated during these tests. No emulator was used.

The app connected by Wi-Fi to port 8001 and the isolated `sevamrita-regression-20261027.local` database. One temporary conversation, **Phone test - Tracker files**, and a three-status tracker were created. Accounts: Ravi Menon (owner), Arjun Sharma (member), Dev Patil (viewer). Existing conversations, roles and user data were retained.

## Passed on the phone

1. Existing login and laptop address survived the APK upgrade. Local demo sign-in and account switching worked.
2. Tracker → Files → Add files opened the full-screen upload editor. Native document-picker navigation and multiple selection worked for text, PDF and PNG fixtures.
3. The editor displayed filenames/sizes and Remove controls. Removing a selected PDF left the text attachment intact. Android disabled the unsupported `.exe` fixture.
4. A file-only upload created one private Note attachment. Database assertions confirmed its stage stayed `quotation`, status stayed Open, and the progress effective date stayed unset.
5. The text file opened in the native preview with its full contents. Android Back returned to the tracker.
6. The full-screen progress editor retained the selected next status, note and two attachments. Back displayed Discard changes; Keep editing preserved all of them.
7. During a controlled connection-failure test, only the local test server was stopped. The failed Post update showed a connection error while retaining the note, status choice, PDF and image. After the server was restored, one retry succeeded.
8. Database assertions confirmed exactly **one** Progress entry with **two** files, moving the tracker from Quotation received to Delivery checked. No duplicate progress or files were created by the failed attempt/retry.
9. PDF and image previews rendered correctly. Attachments were visible and openable from both Files and Updates history. Screenshots were visually inspected.
10. Dev Patil could browse and open the private PDF, with no Add files, Upload files or workflow-update controls.
11. A fourth file added by another local session appeared automatically in the viewer's open Files tab without manual refresh or reopening the tracker. No moving sync indicator was introduced.
12. Save attachment used Android's system destination picker. The exported text file's SHA-256 matched its original contents exactly: `3e0dc664325c5770981d224ee3eefd750e92dedcc1f196b5509e741d7111fa94`.
13. After a controlled force-stop and relaunch, the viewer's login and current server data were retained. Ravi Menon's local session was restored at the end.

No runtime code change or APK rebuild was needed following these phone checks. File types, the 10 MB boundary, five-file limit, pagination, idempotency and role rejection also have the automated coverage recorded in [TRACKER_FILES_TEST_2026-11-08.md](TRACKER_FILES_TEST_2026-11-08.md); large-file boundaries and older Android/OEM versions were not all repeated on the physical device.

## Cleanup and artifacts

- Archived only the temporary phone-test conversation after saving the database assertions. Its test records remain as archived local history.
- Removed only the four fixture files, the exported test file and their dedicated phone Downloads folder. Existing phone files were not modified.
- Left SF testing 0.5.2 installed, signed in as Ravi Menon, on its normal chat list. The local backend was restored and verified on port 8001.
- Local screenshots and test evidence: `/tmp/sf-phone-tracker-files-20261108/`. Android's picker needed to index the ADB-copied fixtures; this was test setup, not an upload defect.
- No Git push, app release/feed publication, production deployment, production Firebase change or production-data mutation was performed.
