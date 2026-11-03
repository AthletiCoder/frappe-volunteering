# Section 8 ERP review — decisions and pending changes

Recorded: 12 October 2026.

## Donation receipt date and financial year

**Status:** Required change noted; implementation pending.

**User decision:** For bank-received donations, use the actual credit date in Sevamrita's bank statement to determine the donation receipt's financial year (1 April–31 March).

- The ERP entry date, acknowledgement issue date and webhook processing date must not determine that FY.
- For payment-gateway donations, use the credit date of the settlement into Sevamrita's bank account for receipt-FY allocation.
- Example: a gateway payment succeeds on 31 March 2026 and is credited to Sevamrita's bank on 2 April 2026. Its bank-receipt FY is 2026–27 under this decision.
- Preserve the original payment, bank credit and entry dates separately for reconciliation and audit.

This records the requested receipt-FY rule, not a conclusion that bank credit determines accounting income recognition in every case. Accruals, conditional grants and corpus treatment remain separate accounting-policy matters for the company's CA. Cash donation dating is outside this bank-credit decision.

No application code or accounting records were changed when recording this note.

## Capital-purchase interface

**Status:** Required creation noted; implementation pending.

**User decision:** Create an interface for recording capital purchases, connected to ERPNext's existing purchase and asset-accounting workflow.

The interface must support:

- Accounts classification of capital expenditure under the company's accounting policy.
- Source invoice recording and posting to the appropriate asset or construction-in-progress account, with the corresponding payable or reimbursement obligation.
- Creation or linking of the asset-register record.
- Purchase and available-for-use dates, and applicable depreciation settings.
- Supporting documents, approvals and the payment link.

Manual classification by Accounts is sufficient; automatic capitalisation decisions are not required.

No application code or accounting records were changed when recording this note.
