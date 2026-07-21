# Frontend handoff — Cashfree donate (for the React Cursor window)

Env / CORS / Cashfree dashboard checklist by environment: **[developer_log_env.md](./developer_log_env.md)**.

Copy this into the other Cursor chat if that window owns the React app.

## Protocol (two Cursor windows)

1. **This window (ERPNext / volunteering):** owns DocTypes, APIs, webhooks, accounting, migrate.
2. **Other window (React):** owns UI, Cashfree JS SDK, Vercel env, routing.
3. **We do not message each other.** You (human) paste this checklist / API contract into the React window when backend changes.
4. **Shared source of truth for APIs:** this file. Update it when backend contracts change.

## Env (React `.env` / Vercel)

```
REACT_APP_ERPNEXT_URL=http://sevamrita.local:8000
```

No trailing slash. No Cashfree secrets in the browser.

## Guest API methods

Base: `{REACT_APP_ERPNEXT_URL}/api/method/`

| Method | Purpose |
|--------|---------|
| `volunteering.volunteering.api.donations.create_donation_and_order` | Create Volunteer+Donation + Cashfree order |
| `volunteering.volunteering.api.donations.get_donation_status` | Poll status (needs `status_token`) |
| `volunteering.volunteering.api.donations.get_donation_receipt_payload` | Thank-you / receipt data |
| `volunteering.volunteering.api.donations.cashfree_webhook` | **Server-only** — Cashfree → ERPNext |

### `create_donation_and_order` body (JSON POST)

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "mobile_number": "9876543210",
  "amount": 500,
  "want_80g": 0,
  "pan": "",
  "address": "",
  "ref": "",
  "return_url": "http://localhost:3000/contribute/thank-you?donation_id={donation_id}&order_id={order_id}"
}
```

If `want_80g: 1` → `pan` + `address` required (PAN format `ABCDE1234F`).

**Response (`message`):** `donation_id`, `payment_session_id`, `status_token`, `environment` (`sandbox`|`production`), `matched_existing_volunteer`, `matched_volunteer_name`, `amount`.

### Checkout

Load Cashfree v3 SDK → `cashfree.checkout({ paymentSessionId, redirectTarget: '_modal' })` with fallback `_self`.

Then poll `get_donation_status` with `donation_id` + `status_token` until Success/Failed.

### Thank-you route

`/contribute/thank-you?donation_id=...&status_token=...`

## ERPNext desk (this window / you)

1. **Cashfree Settings** — App ID, Secret, env, Allowed Origins (React URL), Return URL, Company, MoP, Paid To (Cashfree Clearing).
2. Webhook in Cashfree dashboard →  
   `http://sevamrita.local:8000/api/method/volunteering.volunteering.api.donations.cashfree_webhook`
3. site_config CORS: `"allow_cors": "https://your-react-origin"`
4. Checklist: `apps/volunteering/docs/cashfree_accounting_checklist.md`

## Already implemented in `sevamrita-foundation-website` (if that is the React repo)

- `src/services/erpnextDonationService.js`
- `src/utils/cashfreeCheckout.js`
- `src/components/donate/DonationForm.js`
- `src/components/donate/DonationThankYou.js`
- `/contribute` + `/contribute/thank-you`

If the other window uses a **different** React repo, re-apply those files there using this contract.
