# SF Tasks PWA

A separate installable web app at `/sf-tasks/`, alongside SF Tasks for Android and ERP Home. No Android sources or ERP Home screens are replaced. Conversations and work items use the same permission-checked ERP APIs and database. Access requires **App chat access**; it does not grant **Web chat access** or Desk access.

## Features

- Direct chats, groups, workspaces and subareas; membership levels and archiving.
- Messages, private attachments, replies, editing/removal, mentions, delivery/read ticks and recipient information.
- Full-page task forms, status changes including In progress, subtasks, assignments, deadlines, recurring tasks, postponing and snoozing.
- Status, staged, percentage and numeric trackers; per-stage responsibility, grouped dashboard, pending-with-me highlights, workflow dots, historical snapshots, comments and private supporting files.
- Item-only View/Update sharing retains private chat/comment/file restrictions.
- Events, personal calendar, nested checklists, search, mentions inbox.
- Light, dark and system appearance, safe-area insets and responsive navigation.
- Public offline app shell, account-scoped encrypted IndexedDB snapshots, saved files, message/form drafts and a durable Outbox. Queued mutations use the backend’s fingerprinted replay API. Version/access conflicts require review rather than overwriting newer work.
- Standard Web Push for messages, mentions, assignments and server-scheduled task/tracker reminders; mute/mentions modes, per-conversation settings, quiet hours, binding checks and deduplication. No new Firebase project is needed. The scheduler and queue workers must be running.
- A separate manifest identity and icon. Updates download as website assets; a ready-to-update prompt preserves saved drafts and queued work.

## Build and tests

Use the same frontend toolchain already used by the ERP app:

```sh
npm ci --prefix frontend
npm ci --prefix pwa
npm run build:pwa
npm run test:pwa
```

Built assets are committed under `volunteering/public/sf_tasks/` for Frappe Cloud, as with the existing ERP frontend. Rebuild them whenever `pwa/src` changes. The PWA does not change the existing frontend build command.

Install app Python dependencies and run `bench --site <site> migrate` to create the two private Web Push tables. Run the scheduler and background workers. Server code derives a domain-separated VAPID signing identity from the site's private encryption key; preserve that key across deployments and backups. Its private value never appears in a manifest, API response or browser bundle.

```sh
bench --site sevamrita-regression-20261027.local run-tests --app volunteering --module volunteering.volunteering.test_tasks_pwa
```

`pwa/scripts/http-regression.py` refuses to write unless the local `127.0.0.1:8002` server reports the named isolated regression site. It exercises all core collaboration workflows with the existing demo personas and archives its temporary workspace. It never targets production.

## Local review

```sh
cd /path/to/frappe-bench
bench --site sevamrita-regression-20261027.local serve --port 8002 --noreload
```

Open `http://127.0.0.1:8002/sf-tasks/` on the laptop. Existing local demo accounts work (for example Ravi Menon: `demo.chat.ravi@sevamrita.local`, local-only password `DemoChat!2026`). These accounts/passwords are not created by deployment.

For installation, Web Crypto, service workers and push on a physical phone, use a trusted **HTTPS** origin. Plain `http://<laptop-IP>:8002` is useful for basic page connectivity, but is **not** a valid full PWA/offline/push test. Do not bypass certificate warnings. Production's existing HTTPS host can serve `/sf-tasks/` after an authorized deployment; no deployment is part of this implementation.

## Privacy and browser limits

- Only public shell files enter the service-worker HTTP cache. APIs, private files, login, Desk and ERP Home are not intercepted. Private data is stored separately per account using AES-GCM and a non-exportable local key. This protects the database at rest, but is not a device PIN lock or end-to-end message encryption.
- The session remains the normal ERP session. If the PWA and ERP are on the same origin, signing out also signs out that browser's ERP session. The native Android app keeps its own session.
- Previously saved content is usable offline; permission revocation can only be detected once connected. Known denials clear private snapshots; unsent work remains isolated for review. Signing out removes that account's local snapshots, files, drafts and queue.
- An offline update is not an approved server change until synced. Conflicts remain visible in Outbox. Do not discard queued actions unless you want to remove those unsent changes.
- Browser storage quotas/eviction still apply. Persistent storage can be requested; clearing site data removes offline work. ERP remains the permanent record.
- Background Sync is used when available and foreground/reconnect retries work otherwise. Browsers control closed-app execution. Closed-app reminders need connectivity and Web Push; this is not an exact offline Android alarm replacement.
- Browser/OS permission, battery restrictions, user force-stop and network connectivity affect push. The local automated tests mock the external push service; actual Android/iOS push/install checks require an HTTPS phone session.
- Search uses the online server. Saved files and loaded conversation data are available offline; not every historical attachment is downloaded automatically.

## Push administration

Optional site settings:

- `sf_tasks_pwa_disable_push: true` disables Web Push without affecting native Firebase notifications.
- `sf_tasks_pwa_push_contact` supplies a valid `mailto:` or HTTPS VAPID contact. It defaults to `https://sevamrita.org`.

Only standard browser push hosts are accepted for subscription endpoints; raw URLs cannot make the server call private services. Subscriptions are encrypted Password fields. Server/client notifications contain routing IDs and generic wording, with no message bodies, chat titles, addresses, emails or files sent through push services.
