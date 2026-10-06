"""Explicit, repeatable reorganisation of Sevamrita's existing account tree.

This is deliberately not a migrate hook. Moving an account changes historical
report subtotals, so production use requires a current backup and an accounting
review. Existing account IDs are renamed through ERPNext (which updates Links),
never deleted or merged here.
"""

from __future__ import annotations

import frappe
from frappe import _

from volunteering.volunteering.chart_of_accounts_portal import SEVAMRITA_COMPANY


# Old ERPNext names are retained as the same records, with clearer labels.
# Groups precede their children because ERPNext updates parent Links on rename.
ALIASES = (
	("Asset", "Domestic Bank Account", "Domestic Bank Accounts", 1),
	("Asset", "Sevamrita Foundation Bank", "SF Axis Bank", 0),
	("Liability", "Capital Account", "Funds and Reserves", 1),
	("Liability", "Accounts Payable", "Payables", 1),
	("Liability", "Duties and Taxes", "Statutory Dues", 1),
	("Liability", "Creditors", "Supplier Payables", 0),
	("Liability", "TDS", "TDS Payable", 0),
	("Income", "Direct Income", "Programme and Earned Income", 1),
	("Income", "Indirect Income", "Other Receipts", 1),
	("Income", "Donation Income", "General Donations", 0),
	("Expense", "Direct Expenses", "ERPNext System Accounts", 1),
	("Expense", "Indirect Expenses", "Administration and Operations", 1),
	("Expense", "Print and Stationery", "Printing and Stationery", 0),
)

# The first rehearsal had already made these headings groups, whereas the
# current demo site has the PDF names as posting ledgers. Rename only a group;
# retain a ledger and put it below the broader functional heading.
GROUP_ALIASES = (
	("Employee Costs", "People and Volunteer Costs"),
	("Travel and Conveyance", "Travel and Transport"),
	("Rent and Utilities", "Premises and Utilities"),
	("Professional, Legal and Audit Fees", "Professional Services"),
	("IT and Communication", "Technology and Communications"),
	("Fundraising and Publicity", "Fundraising and Outreach"),
)

LEGACY_GROUPS = {
	"Liability": "Legacy Liability Accounts",
	"Income": "Legacy Income Accounts",
	"Expense": "Legacy Expense Accounts",
}

# (root, account name, parent name or None for the root, group, special type)
# Projects and cost centres identify *where* a cost belongs. Expense accounts
# identify *what* was bought, without forcing a Direct/Indirect split. Create
# only broad expense groups here: Accounts Managers add posting ledgers as the
# actual expenses arise. Existing expense ledgers are kept and reorganised.
NODES = (
	("Asset", "Domestic Bank Accounts", "Bank Accounts", 1, ""),
	("Asset", "FCRA Accounts", "Bank Accounts", 1, ""),
	("Liability", "Funds and Reserves", None, 1, ""),
	("Liability", "Current Liabilities", None, 1, ""),
	("Liability", "Payables", "Current Liabilities", 1, ""),
	("Liability", "Statutory Dues", "Current Liabilities", 1, ""),
	("Liability", "GST Payable / Input GST", "Statutory Dues", 1, ""),
	("Liability", "Supplier Payables", "Payables", 0, "Payable"),
	("Liability", "Employee Reimbursements Payable", "Payables", 0, "Payable"),
	("Liability", "Accrued Expenses", "Current Liabilities", 0, ""),
	("Liability", "TDS Payable", "Statutory Dues", 0, "Tax"),
	("Liability", "PF Payable", "Statutory Dues", 0, ""),
	("Liability", "ESI Payable", "Statutory Dues", 0, ""),
	("Liability", "Grants Received in Advance", "Current Liabilities", 0, ""),
	("Liability", "General Fund", "Funds and Reserves", 0, ""),
	("Liability", "Corpus Fund", "Funds and Reserves", 0, ""),
	("Liability", "Restricted Funds", "Funds and Reserves", 0, ""),
	("Liability", "Surplus / Deficit", "Funds and Reserves", 0, ""),
	("Income", "Donations and Grants", None, 1, ""),
	("Income", "Programme and Earned Income", None, 1, ""),
	("Income", "Other Receipts", None, 1, ""),
	("Income", "General Donations", "Donations and Grants", 0, ""),
	("Income", "Corpus Donations", "Donations and Grants", 0, ""),
	("Income", "Restricted Donations / Grants", "Donations and Grants", 0, ""),
	("Income", "CSR Grants", "Donations and Grants", 0, ""),
	("Income", "Membership Fees", "Programme and Earned Income", 0, ""),
	("Income", "Programme Income", "Programme and Earned Income", 0, ""),
	("Income", "Interest Income", "Other Receipts", 0, ""),
	("Income", "Other Income", "Other Receipts", 0, ""),
	("Expense", "Programme Expenses", None, 1, ""),
	("Expense", "People and Volunteer Costs", None, 1, ""),
	("Expense", "Travel and Transport", None, 1, ""),
	("Expense", "Premises and Utilities", None, 1, ""),
	("Expense", "Professional Services", None, 1, ""),
	("Expense", "Technology and Communications", None, 1, ""),
	("Expense", "Fundraising and Outreach", None, 1, ""),
	("Expense", "Accounting Adjustments", None, 1, ""),
	("Expense", "Administration and Operations", None, 1, ""),
	("Expense", "ERPNext System Accounts", None, 1, ""),
)

# Existing accounts are moved, not re-created, so their references and
# account types remain intact. Names absent from a different chart are skipped.
MOVES = (
	("Asset", "SF Axis Bank", "Domestic Bank Accounts"),
	("Asset", "Cashfree Clearing", "Domestic Bank Accounts"),
	("Liability", "Payroll Payable", "Payables"),
	("Expense", "Beneficiary Supplies", "Programme Expenses"),
	("Expense", "Food and Groceries", "Programme Expenses"),
	("Expense", "Medical Expenses", "Programme Expenses"),
	("Expense", "Education Expenses", "Programme Expenses"),
	("Expense", "Event Expenses", "Programme Expenses"),
	("Expense", "Employee Costs", "People and Volunteer Costs"),
	("Expense", "Travel and Conveyance", "Travel and Transport"),
	("Expense", "Rent and Utilities", "Premises and Utilities"),
	("Expense", "Professional, Legal and Audit Fees", "Professional Services"),
	("Expense", "IT and Communication", "Technology and Communications"),
	("Expense", "Fundraising and Publicity", "Fundraising and Outreach"),
	("Expense", "Unclassified Employee Expenses", "ERPNext System Accounts"),
	("Expense", "Commission on Sales", "ERPNext System Accounts"),
	("Expense", "Sales Expenses", "ERPNext System Accounts"),
	("Expense", "Salary", "People and Volunteer Costs"),
	("Expense", "Travel Expenses", "Travel and Transport"),
	("Expense", "Office Rent", "Premises and Utilities"),
	("Expense", "Utility Expenses", "Premises and Utilities"),
	("Expense", "Legal Expenses", "Professional Services"),
	("Expense", "Telephone Expenses", "Technology and Communications"),
	("Expense", "Telecommunication Expenses", "Technology and Communications"),
	("Expense", "Marketing Expenses", "Fundraising and Outreach"),
	("Expense", "Exchange Gain/Loss", "Accounting Adjustments"),
	("Expense", "Gain/Loss on Asset Disposal", "Accounting Adjustments"),
	("Expense", "Impairment", "Accounting Adjustments"),
	("Expense", "Rounded Off", "Accounting Adjustments"),
	("Expense", "Write Off", "Accounting Adjustments"),
)


def _account(company: str, root_type: str, account_name: str):
	rows = frappe.get_all(
		"Account",
		filters={"company": company, "root_type": root_type, "account_name": account_name},
		fields=["name", "parent_account", "is_group", "account_type", "disabled", "account_number"],
		limit=2,
	)
	if len(rows) > 1:
		frappe.throw(_("More than one {0} account is named {1}.").format(root_type, account_name))
	return rows[0] if rows else None


def _root(company: str, root_type: str):
	root = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": root_type, "parent_account": ["is", "not set"]},
		"name",
	)
	if not root:
		frappe.throw(_("The {0} root account is missing.").format(root_type))
	return root


def preview_sevamrita_chart(company=SEVAMRITA_COMPANY):
	"""Read-only inventory of planned renames, additions, moves and blockers."""
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	roots = {kind: _root(company, kind) for kind in ("Asset", "Liability", "Income", "Expense")}
	aliases = []
	retained_legacy = []
	conflicts = []
	for kind, old, new, is_group in ALIASES:
		source, target = _account(company, kind, old), _account(company, kind, new)
		if source and target:
			if kind == "Asset":
				conflicts.append(f"Both {old} and {new} exist; review the bank accounts before continuing")
			else:
				retained_legacy.append({"existing": source.name, "preferred": target.name})
		elif source and int(source.is_group) != is_group:
			conflicts.append(f"{old} has an unexpected group/ledger type")
		elif kind == "Asset" and old == "Sevamrita Foundation Bank" and source and source.account_type != "Bank":
			conflicts.append(f"{old} must have Account Type Bank")
		elif source:
			aliases.append({"from": source.name, "to": new})
	bank_parent = _account(company, "Asset", "Bank Accounts")
	if not bank_parent or not bank_parent.is_group:
		conflicts.append("Bank Accounts must exist as an Asset group")
	if not (_account(company, "Asset", "SF Axis Bank") or _account(company, "Asset", "Sevamrita Foundation Bank")):
		conflicts.append("SF Axis Bank and its existing ledger alias are both missing")
	if not _account(company, "Asset", "Cashfree Clearing"):
		conflicts.append("Cashfree Clearing is missing")
	for bank_label in ("SF Axis Bank", "Cashfree Clearing"):
		bank = _account(company, "Asset", bank_label)
		if bank and (bank.is_group or bank.account_type != "Bank"):
			conflicts.append(f"{bank_label} must be a Bank posting ledger")
	for old, new in GROUP_ALIASES:
		source, target = _account(company, "Expense", old), _account(company, "Expense", new)
		if source and source.is_group and target:
			conflicts.append(f"Both group accounts {old} and {new} exist")
		elif source and source.is_group:
			aliases.append({"from": source.name, "to": new})
	for kind, label, _parent, is_group, account_type in NODES:
		row = _account(company, kind, label)
		will_rename_group = kind == "Expense" and bool(row and row.is_group) and any(
			old == label for old, _new in GROUP_ALIASES
		)
		if row and int(row.is_group) != is_group and not will_rename_group:
			conflicts.append(f"{label} has an unexpected group/ledger type")
		if row and account_type and not is_group and not will_rename_group and row.account_type != account_type:
			conflicts.append(f"{label} must have Account Type {account_type}")
		if row and row.disabled:
			conflicts.append(f"{label} is disabled")
	created = []
	for kind, label, _parent, _group, _type in NODES:
		row = _account(company, kind, label)
		group_will_be_renamed = kind == "Expense" and bool(row and row.is_group) and any(
			old == label for old, _new in GROUP_ALIASES
		)
		alias_will_create = any(
			alias_kind == kind and new == label and _account(company, kind, old)
			for alias_kind, old, new, _ in ALIASES
		)
		group_alias_will_create = kind == "Expense" and any(
			new == label and (source := _account(company, kind, old)) and source.is_group
			for old, new in GROUP_ALIASES
		)
		if (not row or group_will_be_renamed) and not alias_will_create and not group_alias_will_create:
			created.append(label)
	pending_moves = []
	for kind, label, parent_label in MOVES:
		row = _account(company, kind, label)
		parent = _account(company, kind, parent_label)
		if row and parent and row.parent_account != parent.name:
			pending_moves.append(label)
	return {
		"company": company,
		"roots": roots,
		"rename": aliases,
		"retain_legacy": retained_legacy,
		"create": created,
		"move_existing": pending_moves,
		"posted_gl_entries": frappe.db.count("GL Entry", {"company": company, "is_cancelled": 0}),
		"conflicts": conflicts,
		"note": "No account is deleted or merged. Duplicate old ledgers remain in a legacy group. Parent changes affect historical subtotals.",
	}


def apply_sevamrita_chart(company=SEVAMRITA_COMPANY, *, confirmed=False, allow_posted_entries=False):
	"""Apply the reviewed structure explicitly, never as part of deploy/migrate."""
	if not confirmed:
		frappe.throw(_("Pass confirmed=True only after a current backup and review of the preview."))
	if frappe.session.user != "Administrator":
		frappe.throw(_("Only Administrator may run this chart migration."), frappe.PermissionError)
	preview = preview_sevamrita_chart(company)
	if preview["conflicts"]:
		frappe.throw(_("Resolve chart conflicts first: {0}").format("; ".join(preview["conflicts"])))
	if preview["posted_gl_entries"] and not allow_posted_entries:
		frappe.throw(_("Posted entries exist. Review historical report effects before explicitly allowing reclassification."))

	from erpnext.accounts.doctype.account.account import update_account_number

	renamed = []
	for kind, old, new, _is_group in ALIASES:
		source = _account(company, kind, old)
		if not source or _account(company, kind, new):
			continue
		new_name = update_account_number(source.name, new, source.account_number or None)
		renamed.append({"from": source.name, "to": new_name or source.name})
		frappe.clear_cache(doctype="Account")
	for old, new in GROUP_ALIASES:
		source = _account(company, "Expense", old)
		if not source or not source.is_group:
			continue
		new_name = update_account_number(source.name, new, source.account_number or None)
		renamed.append({"from": source.name, "to": new_name or source.name})
		frappe.clear_cache(doctype="Account")

	created = []
	for kind, label, parent_label, is_group, account_type in NODES:
		if _account(company, kind, label):
			continue
		parent = _account(company, kind, parent_label).name if parent_label else _root(company, kind)
		doc = frappe.get_doc({
			"doctype": "Account", "company": company, "account_name": label,
			"parent_account": parent, "root_type": kind, "is_group": is_group,
			"account_type": account_type,
			"report_type": "Profit and Loss" if kind in ("Income", "Expense") else "Balance Sheet",
		})
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
		frappe.clear_cache(doctype="Account")

	# A partially migrated site can contain both a legacy ledger and its new
	# equivalent. Preserve both and make the older one visibly historical; do
	# not merge GL history or outstanding documents as a side effect of layout.
	legacy_moved = []
	for kind, old, new, _is_group in ALIASES:
		source, target = _account(company, kind, old), _account(company, kind, new)
		if not source or not target:
			continue
		legacy_label = LEGACY_GROUPS[kind]
		legacy = _account(company, kind, legacy_label)
		if not legacy:
			legacy = frappe.get_doc({
				"doctype": "Account", "company": company, "account_name": legacy_label,
				"parent_account": _root(company, kind), "root_type": kind,
				"is_group": 1,
				"report_type": "Profit and Loss" if kind in ("Income", "Expense") else "Balance Sheet",
			})
			legacy.insert(ignore_permissions=True)
			created.append(legacy.name)
		if source.parent_account != legacy.name:
			doc = frappe.get_doc("Account", source.name)
			doc.parent_account = legacy.name
			doc.save(ignore_permissions=True)
			legacy_moved.append({"account": source.name, "parent": legacy.name})
		frappe.clear_cache(doctype="Account")

	moved = legacy_moved
	planned_parents = [(kind, label, parent) for kind, label, parent, _group, _type in NODES]
	planned_parents.extend(MOVES)
	for kind, label, parent_label in planned_parents:
		row = _account(company, kind, label)
		if not row:
			continue
		parent = _account(company, kind, parent_label).name if parent_label else _root(company, kind)
		if row.parent_account == parent:
			continue
		doc = frappe.get_doc("Account", row.name)
		doc.parent_account = parent
		doc.save(ignore_permissions=True)
		moved.append({"account": row.name, "parent": parent})
		frappe.clear_cache(doctype="Account")

	# New supplier documents and claims get separate control accounts. Submitted
	# historical documents keep their own recorded payable account.
	supplier_payable = _account(company, "Liability", "Supplier Payables")
	frappe.db.set_value(
		"Company", company, "default_payable_account", supplier_payable.name,
		update_modified=False,
	)
	employee_payable = _account(company, "Liability", "Employee Reimbursements Payable")
	frappe.db.set_value(
		"Company", company, "default_expense_claim_payable_account", employee_payable.name,
		update_modified=False,
	)
	frappe.clear_cache(doctype="Company")
	if frappe.db.exists("DocType", "Cashfree Settings"):
		legacy_donation = _account(company, "Income", "Donation Income")
		general_donation = _account(company, "Income", "General Donations")
		if legacy_donation and frappe.db.get_single_value("Cashfree Settings", "income_account") == legacy_donation.name:
			frappe.db.set_single_value("Cashfree Settings", "income_account", general_donation.name)
	return {"renamed": renamed, "created": created, "moved": moved,
		"preview": preview_sevamrita_chart(company)}
