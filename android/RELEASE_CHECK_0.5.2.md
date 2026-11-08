# SF Tasks 0.5.2 release check

Version 0.5.2 / code 22 adds private tracker attachments in the Files tab and progress editor, with native previews, multiple selection, safe retries, paginated older files and corresponding web Home controls. It preserves the separate SF Tasks and SF testing packages and their existing signing keys.

Validation is recorded in [TRACKER_FILES_TEST_2026-11-08.md](TRACKER_FILES_TEST_2026-11-08.md) and [PHONE_TRACKER_FILES_TEST_2026-11-08.md](PHONE_TRACKER_FILES_TEST_2026-11-08.md): 90 backend checks, 20 browser regression cases (plus the two file cases rerun after visual polish), 11 frontend checks, 100 Android unit tests per build variant, no lint errors, three release-preparation tests, production web/native builds and physical Android 16 file acceptance. No runtime source changes followed those tests.

The physical check covered file-only uploads preserving progress, status updates with PDF/image evidence, selection/removal, unsaved-change protection, failure/reconnect/retry without duplicates, previews, read-only access, quiet synchronization, saving with a matching checksum and process restart. SF testing 0.5.2 remains installed. Only the temporary test workspace was archived and the dedicated phone fixture folder removed.

## Publication contract

- Commit only intended source, web build assets, tests and documentation to main. Exclude the pre-existing dependency symlink change, output/tmp files, credentials and signing material.
- Target the pushed source commit with the immutable `sf-tasks-v0.5.2` release. Upload the two signed APKs and their checksum files. Verify hosted APK size/hash before replacing either stable update feed.
- Production package: `org.sevamrita.mobile`; testing package: `org.sevamrita.mobile.local`. Both are version code 22, replacing the independently verified code-21 feeds. Preserve their separate package/certificate pins and feeds.
- Publish the stable `sf-tasks-updates` JSON feeds only after both versioned APKs have been verified. Read the public feeds back and verify their referenced downloads and increasing versions.
- The user's request authorizes the source push and app update publication. It does not authorize an ERP production deployment or production Firebase changes. The matching backend update must be deployed separately for production tracker uploads.

Existing updater-capable apps can show the update banner during their normal foreground check or use Check for updates. Android still asks the user to confirm installation. The new SF testing APK was physically checked; installation of the production APK through the update prompt was not performed in this release check.
