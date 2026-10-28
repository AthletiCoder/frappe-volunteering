# Vendor purchases in Home

The **Purchasing** menu separates responsibilities into three standalone pages:

| Page | Route | What appears |
| --- | --- | --- |
| My purchase requests | `/volunteering/vendor-purchases` | Only requests raised by the signed-in user, including drafts, pending, approved and rejected requests. Create, edit or resubmit requests here. |
| Purchase approvals | `/volunteering/purchase-approvals` | Only pending requests currently assigned to the signed-in approver. Review, approve, reject or escalate here. |
| Approved purchases — Accounts | `/volunteering/purchase-accounts` | Approved Home purchases company-wide, for Accounts User / Accounts Manager / Administrator. Record supplier advances, deliveries, bills and payments here. |

A user who is both an employee, an approver and Accounts staff sees all three menu
entries. Their personal page does not contain approval or payment controls;
their approval page does not contain order creation or Accounts controls. The
server checks the perspective for both list and detail access, not just the UI.
The Accounts page has filters for awaiting delivery, awaiting bill, awaiting
payment, and received and billed. Completed orders remain available as history.

Every linked employee, including managers and Accounts staff, sees their active
member projects at the top of Home. Select a project's title to view its details,
or **Place purchase order** to open a new purchase with that eligible project
already selected. This does not broaden membership or financial permissions.
The existing Board of Directors restriction on raising POs remains enforced;
their project card keeps the purchase button disabled.

## Roles and sequence

1. An active employee selects an approved active project they belong to, a supplier, items, quantities, **unit prices including taxes**, expected delivery, and an optional quotation. There is no tax-template selector in Home order entry. Accounts employees can raise purchases across active projects. Save a draft or submit it for the existing Purchase Order approval workflow.
2. The assigned approver opens **Purchase approvals**, or the same dedicated page from Home's waiting list. Review notes and approve/reject/escalate actions are at the end of the detail page. After a decision, the request leaves that approver's pending queue. Existing grade authority and budget checks remain in effect. Rejected requests can be edited and submitted again by their requester in **My purchase requests**.
3. Accounts opens **Approved purchases — Accounts** and records an actual advance payment against the approved order, with the source bank/cash ledger, amount, posting date and bank reference. The request does not initiate a bank transfer.
4. The requester or Accounts records quantities actually received. Partial deliveries create separate standard Purchase Receipts linked to the order. Stock items require a receiving warehouse.
5. Accounts selects a delivery and records its supplier bill, including invoice number, invoice date, expense accounts and a mandatory private attachment. The invoice accounting date is the invoice date. Standard ERPNext mapping carries the order's gross rates to the receipt and bill. Accounts can optionally record the included tax breakup per bill item; it does not add tax or change the expense/stock cost. Earlier advances allocated to that exact order are applied to the bill.
6. Accounts records a payment against the outstanding supplier invoice. Additional partial payments are supported. The detail page displays bills, deliveries, payments, private evidence, advance applied and the amount still payable.

Unpaid Home supplier invoices appear in Accounts' waiting queue and link to the
Accounts page filtered to purchases awaiting payment. Old
`/volunteering/vendor-purchases?view=payments` links redirect there as well.

## Initial setup

An Accounts Manager can use **Enable supplier advances** on **Approved purchases — Accounts**. This enables ERPNext's separate-party advance accounting and uses the company's configured supplier advance account. If none is configured, it uses or creates **Vendor Advances**, an Asset / Receivable ledger. An unused existing ledger without a special type can be corrected; a used or conflicting ledger requires explicit Accounts review in Chart of Accounts.

Accounts Managers can register suppliers and create consumption/service item masters from the Accounts page. Existing basic stock items and warehouses can be selected. Asset purchases and items requiring serial or batch tracking need their specialized ERPNext processing; they are excluded from this item selector.

New Home orders use tax-inclusive prices and suppress automatic additional taxes from default or item tax templates. Existing orders with ERP tax rows keep their existing tax treatment; Home does not allow those templates to be changed or a second included-tax breakup to be added. This screen does not create tax rules, withholding configurations or statutory returns.

## Optional tax breakup for Accounts

In **Record supplier bill**, Accounts User / Accounts Manager can check **Record included tax breakup (optional)**. Enter the actual CGST, SGST/UTGST, IGST or other tax amounts included in each item. The value before included taxes and the unchanged gross total are calculated automatically. Use either IGST or CGST/SGST for a given item. Negative amounts, more than two decimal places, unrelated/repeated bill items and taxes exceeding an item's gross amount are rejected on both client and server.

Sevamrita is currently not GST registered. This is a reference record only, stored with the Purchase Invoice and visible in its Accounts-only tax-breakup detail. It does **not** create recoverable GST or an input-tax ledger posting. A gross INR 1,180 purchase with INR 180 included tax still charges INR 1,180 to its expense/stock cost and creates INR 1,180 payable before advance adjustment. The stored reference says INR 1,000 value before taxes plus INR 180 tax. Leaving this unchecked records the same gross accounting entries without the additional metadata. The original supplier bill remains private evidence in either case.

## Accounting example

For ₹1,00,000 of immediately consumed materials with a ₹50,000 bank advance:

| Action | Debit | Credit | Amount |
| --- | --- | --- | ---: |
| Record supplier advance | Vendor Advances | Bank | ₹50,000 |
| Post full supplier bill | Materials expense | Supplier Payables | ₹1,00,000 |
| Apply the order advance | Supplier Payables | Vendor Advances | ₹50,000 |
| Record final payment | Supplier Payables | Bank | ₹50,000 |

The Purchase Order itself creates no GL Entry. Stock receipts use ERPNext's inventory accounting instead of immediately charging an expense. A posted Home supplier bill replaces its corresponding project purchase-order commitment in the financial summary. Paying it does not consume the project budget a second time.

## Data and controls

- Standard Purchase Order, Purchase Receipt, Purchase Invoice and Payment Entry documents remain the source records.
- Unique request keys protect against repeated submissions. Order locks, quantity/payment ceilings and invoice-number checks prevent duplicate or excess postings.
- Requesters can see only their purchases. Assigned approvers can access orders awaiting their review. Accounts can manage Home purchases company-wide.
- ERP currency validation receives temporary access to the exact supplier control-account definition during the operation. That access is removed before the request commits. Employees receive no lasting account, balance-report or ledger permission.
- New Home purchases have a marker. Existing Desk-only test orders are not adopted or displayed by this workspace.
- The normal accounting migration installs the added fields. No production deployment or data migration is performed by creating these source changes.

## Verification

Real database lifecycle and ledger checks:

```sh
bench --site sevamrita.local run-tests --module volunteering.volunteering.test_vendor_purchases --skip-before-tests
```

Browser interaction and phone-layout checks (deterministic API fixtures; real Vue screens):

```sh
node node_modules/@playwright/test/cli.js test -c playwright.purchasing.config.ts
```

The browser fixture tests do not post live transactions. The Python integration tests separately exercise real ERP documents, permissions, private attachments, receipt quantities, invoice dates, advance reconciliation, final payment and ledger effects.
