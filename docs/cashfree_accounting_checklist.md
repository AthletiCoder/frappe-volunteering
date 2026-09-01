# Cashfree donations — accounting checklist (production)

Complete these steps in ERPNext **before** switching Cashfree Settings to production.

## 1. Company
- Confirm the Sec 8 Company exists with an India chart of accounts.

## 2. Ledger: Cashfree Clearing
- Chart of Accounts → create **Cashfree Clearing** under Bank Accounts (Account Type: Bank).
- This holds gateway receipts until settlement hits your real bank.

## 3. Ledger: Donation Income
- Create **Donation Income** (Income / as advised by your CA for Sec 8).
- Store the account name in **Cashfree Settings → Donation Income Account**.
- On each successful donation (when Auto Create Payment Entry is on), the app posts:
  - **Payment Entry (Receive):** Debit Cashfree Clearing / Credit Debtors
  - **Journal Entry:** Debit Debtors / Credit Donation Income

## 4. Mode of Payment
- Accounts → Mode of Payment → **Cashfree**.
- Default Account = Cashfree Clearing (for your Company).

## 5. Cashfree Settings (Volunteering)
- Environment: sandbox first, then production.
- App ID + Secret Key from Cashfree dashboard.
- Allowed Origins: your Vercel URL(s), e.g. `https://www.sevamrita.org,https://sevamrita-foundation.vercel.app`
- Return URL: `https://YOUR-SITE/contribute/thank-you?donation_id={donation_id}&order_id={order_id}`
- Company, Mode of Payment, Paid To = Cashfree Clearing.
- Enable Auto Create Payment Entry.
- Org display name, 12A / 80G registration numbers for acknowledgements.
- Min amount 100; set fraud caps as needed.

## 6. Cashfree dashboard + CORS
- Whitelist your website domain in Cashfree.
- Webhook URL: `https://YOUR-ERPNEXT/api/method/volunteering.volunteering.api.donations.cashfree_webhook`
- Subscribe to payment success / failed events.
- Use the same secret used for signature verification (client secret or dedicated webhook secret in Settings).
- In `site_config.json` (or common_site_config), set CORS for the React origin, e.g.:
  `"allow_cors": "https://www.sevamrita.org"`
  (or a list of origins if your Frappe version supports it). Also fill **Cashfree Settings → Allowed Origins**.

## 7. Email
- Configure an Email Account in Frappe for donor acknowledgements and the daily digest (free / your SMTP).

## 8. Settlement (ops)
- When Cashfree settles to bank, post a Journal Entry: Debit Bank / Credit Cashfree Clearing for the net settlement (fees as CA advises).

## 9. Migrate
```bash
bench --site YOUR_SITE migrate
bench --site YOUR_SITE clear-cache
```

Migrate seeds **Cashfree Clearing**, **Donation Income**, **Cashfree** mode of payment, and fills empty Cashfree Settings accounting fields (it does not override an existing Paid To / Income Account / Auto Create flag).

## 10. Smoke test (sandbox)
1. Donate ₹100 from React with 80G off.
2. Confirm Donation → Pending → Success, Payment Entry and income Journal Entry created.
3. Donate with 80G on + valid PAN + address.
4. Force-fail a payment; status Failed; no PE or JE.
5. Confirm daily digest job is scheduled (`bench doctor` / scheduler).
