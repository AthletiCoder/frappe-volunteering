# Expense Receipt Review

Expense Claims pass an independent receipt check before they reach the spending
approver. Receipt review checks the evidence; it does not approve the expense or
make a payment.

## Workflow

1. The employee saves the claim, attaches at least one private PDF, PNG, JPG, or
   JPEG receipt, and selects **Submit**.
2. The claim enters **Pending Receipt Review**. No manager is assigned yet.
3. A user with the **Expense Receipt Reviewer** role opens the claim and either:
   - completes the checklist and selects **Verify Receipts**, moving the claim to
     **Pending Approval**; or
   - selects **Request Correction**, adds required notes, and returns the claim
     to the employee as **Receipt Correction Required**.
4. After verification, the existing grade and Reports To routing assigns the
   manager or higher approver. Manager approval submits the claim as **Approved**.
5. Accounts creates and submits the Payment Entry. The normal Expense Claim
   status becomes **Paid** when it is fully settled.

## Reviewer controls

The reviewer can read claims in the receipt-review queue and inspect their
attachments. The role has no permission to edit claim amounts, approve spending,
read the Chart of Accounts, create Payment Entries, or settle reimbursements. A
reviewer cannot review their own claim.

Verification records the reviewer, timestamp, notes, checklist result, and an
attachment snapshot containing file identifiers and content hashes. Changing any
attachment before manager approval invalidates verification and sends the claim
back to **Pending Receipt Review**. Attachments are locked after approval; cancel
and amend the claim if its evidence must change.

Accounts cannot submit a Payment Entry against an Expense Claim unless the claim
is approved, its receipt status is **Verified**, and its current attachments match
the reviewed snapshot.

## Setup

Assign **Expense Receipt Reviewer** on the reviewer's User record. Do not also
grant Accounts User, Accounts Manager, Expense Approver, or additional accounting
permissions unless that person independently performs those duties.

Migration moves unapproved claims that were already awaiting a manager back to
receipt review. Historical approved claims are not silently certified; a reviewer
must verify them retrospectively before a new reimbursement Payment Entry can be
submitted.
