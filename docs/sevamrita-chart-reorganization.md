# Sevamrita chart reorganisation

This replaces the generic *Direct/Indirect* presentation with accounts that
describe Sevamrita's activities. Project and Cost Center carry the purpose of
an expense; the account identifies what was purchased. The September 2026
Section 8 PDF is a starting reference, not a direction to overwrite ERPNext's
existing Company chart.

## Intended hierarchy

- **Application of Funds (Assets):** Bank Accounts contains Domestic Bank
  Accounts, with the existing SF Axis Bank and Cashfree Clearing ledgers, and
  an empty FCRA Accounts group. The existing singular Domestic Bank Account
  group is renamed rather than duplicated. On the restored production chart,
  the existing Sevamrita Foundation Bank ledger is renamed to SF Axis Bank;
  its linked transactions are retained. No FCRA bank ledger is created.
  Other asset groups and the existing Cash, Employee Advances (Receivable),
  and Temporary Opening ledgers remain unchanged. This grouping does not by
  itself configure FCRA banking or establish regulatory compliance.
- **Source of Funds:** Current Liabilities contains Payables and Statutory Dues.
  Existing Creditors becomes Supplier Payables only if that target does not
  already exist; otherwise Creditors stays under Legacy Liability Accounts. A separate Employee
  Reimbursements Payable ledger becomes the default for *new* claims. Existing
  TDS becomes TDS Payable. Funds and Reserves replaces the generic Capital
  Account heading. Existing payroll, loan and stock-control accounts remain.
- **Income:** Donations and Grants contains General, Corpus, Restricted and CSR
  donations. Programme and Earned Income contains programme income, membership,
  and the pre-existing ERPNext Sales/Service ledgers. Other Receipts contains
  interest and other income. The Cashfree setup uses General Donations rather
  than re-creating Donation Income.
- **Expenses:** Programme Expenses can contain beneficiary supplies, food,
  medical, education and event costs when those ledgers are needed. People and
  Volunteer Costs, Travel and Transport,
  Premises and Utilities, Professional Services, Technology and Communications,
  Fundraising and Outreach, Administration and Operations, Accounting
  Adjustments, and ERPNext System Accounts organise any existing leaves by
  their nature. The reorganisation does **not** create the PDF's optional
  expense posting ledgers. If Employee Costs or Travel and Conveyance already
  exists, it is placed beneath the relevant group. A travel expense for a
  programme stays under Travel; its Project supplies the programme context.

Accounts Managers can add a new expense posting ledger from Home → Accounts →
Chart of Accounts when a real expense first needs that classification. Choose
the appropriate existing group as parent and create a **ledger**, not another
group, unless a further hierarchy is genuinely needed. Review the account
type and name before using it on a claim. Claims may await Accounts
classification until the needed ledger is created; the migration does not
pre-populate a catalogue of hypothetical expenses.

The combined GST heading is only a group, not a posting ledger. Input GST and
GST payable require separate treatment if applicable. Corpus and restricted
funds need accounting-policy review before any postings. Do not treat the new
fund accounts as interchangeable with donation income accounts.

## Controlled application

1. Obtain a fresh full site backup and verify it can be restored. Preview on a
   restored local site first:

   `bench --site SITE execute volunteering.volunteering.sevamrita_chart_reorganization.preview_sevamrita_chart`

2. Review every rename and creation. If both old and new names for either the
   Domestic Bank Accounts group or SF Axis Bank ledger exist, resolve that
   conflict manually; the migration will stop rather than merge bank accounts.
   For other aliases, if
   both old and target exist, the old account is retained in a clearly labelled
   Legacy group. Decide separately whether any old balance needs a
   documented accounting adjustment. The migration also refuses to run over
   posted GL entries unless the operator explicitly accepts historical report
   reclassification after an accountant's review.
3. On the reviewed copy, apply explicitly:

   `bench --site SITE execute volunteering.volunteering.sevamrita_chart_reorganization.apply_sevamrita_chart --kwargs '{"confirmed": True}'`

   If the site has posted GL entries and their historical report presentation
   has been reviewed, pass `"allow_posted_entries": True` in the kwargs too.

4. Check the tree, Company defaults, Cashfree settings, Expense Claim Type
   accounts, Project expense mappings, and a donation, advance, expense claim,
   and reimbursement rehearsal. Compare Trial Balance and P&L before/after.

The migration renames and moves Account records through ERPNext, preserving
Links; it creates missing accounts but never deletes or merges an account. If
an old and a PDF account already coexist, the old record moves under an
explicit Legacy group; its transactions are not silently combined with the
preferred ledger. The requested bank grouping is the only Application of
Funds change. Production uses a one-time, site-scoped patch in
`volunteering/patches.txt`. After deploying that commit, run **In-Place Migrate
Site** in Frappe Cloud; deploying Python code alone does not apply the database
reorganisation. The patch stops before changing accounts if the live chart has
conflicts or any posted GL entries. Frappe records successful patches so later
migrations do not repeat the change. On other sites, the explicit preview/apply
commands above remain available for a reviewed rehearsal.
Existing submitted claims may retain their original payable account; the new
Company default applies to claims created after the change.
