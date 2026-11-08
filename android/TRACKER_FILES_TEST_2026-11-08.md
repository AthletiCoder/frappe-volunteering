# Tracker attachments — 8 November 2026

SF Tasks and SF testing 0.5.2 / version code 22 add private tracker documents through the Files tab and the full-screen progress editor. Web Home provides the corresponding tracker Files action and progress attachments. Existing messages and attachment permissions are preserved.

## Behaviour

- Up to five PDF, supported image, text/CSV, DOCX or XLSX files per upload/update; each file must be non-empty and at most 10 MB.
- File-only uploads create a dated note linked to the tracker, without changing its progress, status or progress effective date. Progress attachments belong to the same progress entry and snapshot.
- A separate paginated Files query retains access to documents outside the most recent 100 history entries. Files show their uploader, size, timestamp and optional note.
- Conversation members can read files. Existing read-only members and archived conversations cannot upload. Item-only shares do not grant access to conversation attachments.
- The full batch is validated before progress changes. Unique, content-checked request keys protect retries from duplicate files or progress entries. Stale versions, changed retry payloads, revoked roles and deleted entries are checked server-side.
- Native PDF/image/text preview and Save attachment are reused. Word/Excel files can be saved for a compatible app.

## Final validation

| Check | Result |
| --- | --- |
| Backend collaboration, including eight new tracker-file cases | 65 passed |
| Independent web/app role enforcement | 8 passed |
| Notification integration (Google delivery mocked) | 17 passed |
| Collaboration browser regression | 20 passed |
| Tracker upload browser cases rerun after final visual polish | 2 passed |
| Frontend regression | 11 passed |
| Android Debug unit tests | 100 passed, no failures/errors/skips |
| Android Release unit tests | 100 passed, no failures/errors/skips |
| Debug/Release lint | Zero errors; no warnings on the changed Kotlin files |
| Web production build | Passed |
| Signed native builds | Both variants passed |
| Release preparation tests | 3 passed |
| Physical Android 16 phone acceptance | Passed; see PHONE_TRACKER_FILES_TEST_2026-11-08.md |
| APK preparation | Both package IDs, version 22, existing certificate pins, hashes and sizes verified |

The two new browser flows cover independent uploads, progress attachments, actual private-file HTTP reads, viewer access, signed-out denial, invalid extensions, removal, stale-update rejection, retained file selections and a 390px layout without horizontal overflow. Backend cases additionally exercise retries, complete-batch validation, pagination, long history, cross-tracker cursors, deleted notes, archived trackers, revoked roles and app-only users.

One early browser run assumed a literal filename; it was corrected to allow the storage-generated content suffix. Another run overlapped Android compilation and encountered local timeouts. The final full browser run was performed without the Android build and passed. Testing also found a clickable-looking Close button during the final refresh; it now correctly disables while busy.

Browser writes used only the isolated local regression site on localhost:8002. Live push sending was disabled during each browser run and restored afterwards. Only the temporary workspaces created by each run were archived. No production data was used. Visual screenshots were reviewed for desktop and mobile web. The subsequent physical Android 16 acceptance check passed the upload, preview, retry, read-only, quiet-sync, export and restart cases recorded in [PHONE_TRACKER_FILES_TEST_2026-11-08.md](PHONE_TRACKER_FILES_TEST_2026-11-08.md).

## Local artifacts and deployment state

- Signed APKs and checksum/feed metadata: `output/sf-tasks-0.5.2/` (ignored local artifacts).
- The SF testing backend was restarted on port 8001 with the new implementation. The laptop Wi-Fi address was verified as `192.168.29.204` at completion.
- The temporary port-8002 regression server was stopped after testing.
- The implementation and phone-validation runs did not commit/push code, publish an app update/feed, deploy ERP production, change production Firebase settings, or operate the production app on the phone. The subsequently requested source/app publication is covered by [RELEASE_CHECK_0.5.2.md](RELEASE_CHECK_0.5.2.md). The SF testing APK was subsequently installed for the separately requested physical test. Production file controls require the matching backend deployment and the new APK.
