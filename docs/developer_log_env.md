# Developer log — Cashfree donations env & config

Track what to set per environment. **Never commit real secrets** (Cashfree keys, DB passwords). Update the “Last verified” column when you change something.

Related: [frontend_handoff_cashfree.md](./frontend_handoff_cashfree.md) · [cashfree_accounting_checklist.md](./cashfree_accounting_checklist.md)

---

## Environments at a glance

| Env | React host | ERPNext host | Cashfree env |
|-----|------------|--------------|--------------|
| Local | `http://localhost:3000` | `http://sevamrita.local:8000` (or your bench URL) | `sandbox` |
| Staging | _(fill)_ | _(fill)_ | `sandbox` |
| Production | _(fill e.g. https://www.sevamrita.org)_ | _(fill)_ | `production` |

---

## 1. React (Vercel / `.env`)

| Variable | Local | Staging | Production | Notes |
|----------|-------|---------|------------|-------|
| `REACT_APP_ERPNEXT_URL` | `http://sevamrita.local:8000` | | | No trailing slash |
| `REACT_APP_API_BASE_URL` | legacy Java API if used | | | Unrelated to Cashfree |
| `REACT_APP_ENV` | `development` | `staging` | `production` | Optional |

**Where:** repo `.env` (local) · Vercel Project → Settings → Environment Variables  

**Last verified:** 2026-07-11 — local donate flow working with ERPNext URL set  

---

## 2. ERPNext `site_config.json` (or `common_site_config.json`)

| Key | Local | Staging | Production | Notes |
|-----|-------|---------|------------|-------|
| `allow_cors` | `http://localhost:3000` | React staging origin | React prod origin | Must match browser Origin header |
| `developer_mode` | `1` | `0` | `0` | |
| `encryption_key` | (site-specific) | | | Used for donation `status_token`; don’t rotate casually |

**Where:** `sites/<site>/site_config.json`  

**Last verified:** 2026-07-11 — local `allow_cors` = `http://localhost:3000`  

---

## 3. Desk → **Cashfree Settings** (Single)

| Field | Local | Staging | Production | Notes |
|-------|-------|---------|------------|-------|
| Environment | `sandbox` | `sandbox` | `production` | |
| App ID | sandbox App ID | sandbox / staging | **prod** App ID | From Cashfree dashboard |
| Secret Key | sandbox secret | | **prod** secret | Password field; never in git |
| Webhook Secret | usually = Secret Key | | | Must match Cashfree signing secret |
| Allowed Origins | `http://localhost:3000,http://127.0.0.1:3000` | staging URL(s) | prod URL(s) | Comma-separated |
| Return URL | `http://localhost:3000/contribute/thank-you?donation_id={donation_id}&order_id={order_id}` | staging thank-you URL | prod thank-you URL | Placeholders replaced server-side |
| Company | Sevamrita Foundation | | | |
| Mode of Payment | Cashfree | | | |
| Paid To | Cashfree Clearing - SF | | | Clearing ledger |
| Income Account | Donation Income - SF | | | Reference / CA |
| Auto Create Payment Entry | ✓ | ✓ | ✓ | |
| Min amount | 100 | 100 | 100 | |
| Org / 12A / 80G numbers | optional in sandbox | fill | fill | Receipts / digests |
| Digest recipients | (empty = Accounts + System Manager) | | | Comma-separated emails |

**Last verified:** 2026-07-11 — sandbox keys configured; accounting stubs created  

---

## 4. Cashfree merchant dashboard

| Setting | Local | Staging | Production |
|---------|-------|---------|------------|
| Domain whitelist | localhost / ngrok host | staging domain | prod domain |
| Webhook URL | Needs **public** URL → `{ERPNEXT}/api/method/volunteering.volunteering.api.donations.cashfree_webhook` | same pattern | same pattern |
| Webhook events | Payment success + failed | same | same |
| API keys | Sandbox | Sandbox or test | Production |

**Local webhook tip:** use ngrok/cloudflared to expose ERPNext, or rely on status poll + 15‑min reconcile job if webhook can’t reach localhost.

**Last verified:** _(fill when you set webhook)_  

---

## 5. Frappe Email (optional but recommended)

| Setting | Purpose |
|---------|---------|
| Email Account | Donor acknowledgement + daily donation digest |
| Digest | Scheduled daily via `send_daily_donation_digest` |

**Last verified:** _(not required for payment to succeed)_  

---

## 6. Scheduler / ops

| Item | Notes |
|------|-------|
| `*/15 * * * *` reconcile | `volunteering.volunteering.api.reconcile.reconcile_pending_donations` |
| Daily digest | `volunteering.volunteering.api.digest.send_daily_donation_digest` |
| Settlement JV | When Cashfree pays out: Debit Bank / Credit Cashfree Clearing |

Ensure `bench start` / production supervisor has the scheduler enabled.

## 7. Running payment tests

```bash
bench --site sevamrita.local run-tests --app volunteering --module volunteering.volunteering.doctype.donation.test_donation
bench --site sevamrita.local run-tests --app volunteering --module volunteering.volunteering.api.test_donations
bench --site sevamrita.local run-tests --app volunteering --module volunteering.volunteering.api.test_payment_entry
```

Cashfree HTTP is mocked — no live gateway calls. Do not put real secrets in tests.

---

## Change log

| Date | Who | Change |
|------|-----|--------|
| 2026-07-11 | | Sandbox Cashfree Settings + Clearing/MoP/Income; local CORS; React `REACT_APP_ERPNEXT_URL`; end-to-end donate confirmed working |
| 2026-07-12 | | Added donation/Cashfree test suite (unit + integration, Cashfree mocked) |
| | | |
