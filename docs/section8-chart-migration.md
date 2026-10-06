# Sevamrita Section 8 chart migration

The September 2026 chart PDF is a **starter**, not an approved accounting policy. The
`section8_chart` template adds its accounts to the existing ERPNext tree. It never
renames, moves, disables, or deletes an account during `bench migrate` or app deploy.

## Decisions for the Chartered Accountant

- Confirm whether corpus and restricted receipts belong in Income, Funds/Reserves,
  or deferred liabilities for the relevant reporting period. The starter PDF lists
  both Corpus Donations (Income) and Corpus Fund (Funds/Reserves); they must not be
  treated as interchangeable posting accounts.
- Separate input GST from GST payable before posting tax. The combined PDF label is
  created as a **group**, not a ledger, precisely to avoid netting them by accident.
- Confirm whether FCRA registration is in force before adding an FCRA heading or
  posting any foreign contribution. The default template skips the optional heading.
- Confirm donor-identification thresholds and the statutory donation statement and
  certificate forms applicable to each tax year. A portal receipt is only an
  acknowledgement; it is not a substitute for the tax department's certificate.
- Map the existing Cashfree Clearing, bank, cash, employee payable, employee advance,
  project expense accounts, Company defaults, and payment modes to the approved
  chart. Do not create a generic “Domestic Bank Account” posting ledger; the template
  makes it a group so each actual bank has a distinct ledger.

## Rehearsal and rollout

1. Take a verified full site backup (database plus private/public files). Retain it
   outside the bench being updated.
2. Compare live GL entry counts, opening balances, Company default accounts,
   Payment Entry modes, project-account mappings, and settings that link to Account.
   “No ledger entries” does not mean an account has no references.
3. Run `bench --site SITE execute volunteering.volunteering.section8_chart.preview_section8_chart`
   on a fresh staging copy. Review every `existing`, `create`, and `conflict` row.
4. Resolve conflicts and obtain CA sign-off on the classifications above. Rehearse
   donation, advance, expense claim, Cashfree, bank and financial reports on staging.
5. Only after approval, explicitly run
   `bench --site SITE execute volunteering.volunteering.section8_chart.apply_section8_chart --kwargs '{"confirmed": True}'`.
   Set `include_fcra` only where relevant. Running it again is idempotent.
6. Decide separately which legacy ledgers to retain, rename, disable, or transfer.
   Do not delete a used ledger or bulk-replace ERPNext's account table. Reconcile the
   Trial Balance and bank balances before allowing production posting.

The Home donation form posts Dr selected Cash/Bank, Cr selected Income/Equity ledger
as one Journal Entry and freezes a private acknowledgement PDF. The credit account
selection is an Accounts Manager responsibility; it does not auto-classify corpus or
restricted donations. Existing online/Cashfree donations continue using their
existing clearing and income settings until those mappings are explicitly reviewed.
