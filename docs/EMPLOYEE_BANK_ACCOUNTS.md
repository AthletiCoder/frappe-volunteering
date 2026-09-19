# Employee reimbursement bank accounts

Employees open **Home → My reimbursement bank account**. They enter the account-holder name, bank, account type, account number twice and IFSC, optionally branch/SWIFT, attach private bank proof, and confirm ownership. PDF, PNG and JPEG proof up to 5 MB is accepted. Validation checks syntax and confirmation; it does not verify the bank externally.

Only an **Accounts Manager** can approve, return for correction or reject a request. **Accounts User**, Projects Manager, Expense Approver and System Manager alone do not grant this authority. Frappe's built-in Administrator remains a superuser. Managers use **Home → Review reimbursement bank accounts**, or the pending item under Waiting on you. Return/reject requires comments. The manager should compare holder, account number and IFSC against the proof before approval.

## Approval and changes

- Pending requests do not create usable ERPNext Bank Accounts. One pending request per employee is allowed.
- Approval creates a default, non-company **Bank Account** with party type Employee, linked to that employee.
- An existing approved destination stays usable while a replacement is pending, returned or rejected.
- Approval of a replacement supersedes the earlier request and disables its linked Bank Account. Each approval creates a new record, preserving historical destinations even if the last four digits match.
- Returned/rejected requests are retained. The employee submits a new corrected request, rather than rewriting the previous one.
- Requests retain submitter, submission time, proof, ownership confirmation, status, reviewer, decision time and comments. Direct request/proof edits, deletion and sharing are blocked.
- Employee reimbursement Bank Account creation/changes go through this workflow, not direct Desk edits. Existing legacy bank records are not automatically trusted or approved.
- Employee payroll bank fields are not changed by this workflow.

## Remittance and documents

Employee **Pay** Payment Entries from a **Bank** ledger require the current approved destination. An empty Party Bank Account is filled on save; a different or superseded destination is rejected. The destination is checked again before submission, including for drafts saved before a replacement approval. Cash payments do not require a personal bank account; all existing claim/advance approval, receipt-review and cash-limit controls still apply. This records a payment destination and does not itself initiate a real bank transfer.

**Prepare an invoice** uses the same approved record for both GST/non-GST PDFs and Word documents. It requires an approved account. The employee cannot edit remittance fields there; the server ignores any client-supplied bank details. The form lets the employee choose supplier signature or volunteer signature, without a separate signature-acknowledgment checkbox. Both choices use the source-format heading (**INVOICE** or **TAX INVOICE**) and fields. For volunteer signing, the server uses the logged-in employee's identity and labels only the signature block accordingly; it does not add workflow or reimbursement wording to the invoice. The supplier non-GST registration declaration is hidden from the form, but included in generated non-GST PDF and Word documents only when the supplier signs. It is absent from volunteer-signed and GST documents. It never presents the volunteer as signing for the supplier.

The form has separate **Generate PDF** and **Generate Word** buttons; only the chosen format is generated and downloaded. HSN/SAC is optional for each item in both forms; a missing code remains blank in the documents. Supplier PAN is optional for non-GST invoices, but must have the correct syntax if supplied. The buyer normally means Sevamrita Foundation, not the volunteer paying on its behalf; the consignee is the recipient of the goods.

Form-generated invoice numbers are assigned by the server on generation: `INV-2026-000001`, `INV-2026-000002`, etc. One persistent sequence is shared across all employees and GST/non-GST forms, resetting for each calendar **generation year**, independently of the invoice date entered. Generating the other format for the unchanged form preserves the number using an authenticated server-issued reference bound to the employee and complete document content, including approved bank details. Editing content or changed approved bank details requires a new number. Repeated downloads do not allocate a number. Invalid submissions and failed generation transactions do not consume a number. This does not renumber previously generated invoices or ERP accounting documents.

Employees see masked account numbers on the portal and their own request history. Accounts Managers see full numbers in their approval queue. Downloaded invoice documents include the full approved number as needed for remittance, so treat them as sensitive. Proof is private and accessible only to its submitter and Accounts Managers. The submitted number uses Frappe's encrypted Password storage; the approved ERPNext Bank Account uses ERPNext's standard account-number field and existing finance-role access. No new Chart of Accounts or Accounts User permissions are granted to employees.

## Deployment and verification

Back up the site, deploy the branch, run `bench --site YOUR_SITE migrate`, rebuild frontend assets, clear caches and restart workers/web processes as usual. This adds a new DocType; it does not replace the database or approve legacy data. Have employees submit existing bank details for Accounts Manager review before using bank reimbursement or the invoice generator.

Backend tests:

```bash
bench --site sevamrita.local run-tests --app volunteering --module volunteering.volunteering.test_employee_bank_accounts
```

Browser tests are explicitly local-only, without the full-site seeder:

```bash
BASE_URL=http://127.0.0.1:8001 npx playwright test --config playwright.bank-accounts.config.ts
```

They use the existing local associate, Accounts User and Accounts Manager demo personas. They submit and approve fictional bank details for the associate and retain these as local demonstration history. Never run them against staging or production. PDF/Word downloads are stored in ignored `test-results/bank-accounts/` for inspection.
