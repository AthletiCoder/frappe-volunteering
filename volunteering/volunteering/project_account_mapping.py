"""Accounts-Manager-only ledger mapping, separate from approved label budgets."""

import json
from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, now_datetime

_mapping = ContextVar("project_account_mapping", default=None)


def can_map(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or (user != "Guest" and "Accounts Manager" in frappe.get_roles(user))


@contextmanager
def mapping_context(project):
	"""Internal context, never a Document flag or a client-supplied argument."""
	if not can_map():
		frappe.throw(_("Only Accounts Managers may map expense labels to accounts."), frappe.PermissionError)
	token = _mapping.set(project)
	try:
		yield
	finally:
		_mapping.reset(token)


def _mapping_values(doc):
	values = {}
	for row in doc.get("expense_account_mappings") or []:
		values.setdefault(row.budget_key, [])
		if row.expense_account and row.expense_account not in values[row.budget_key]:
			values[row.budget_key].append(row.expense_account)
	return {key: sorted(accounts) for key, accounts in values.items()}


def _legacy_ledger_values(doc):
	return {
		row.budget_key: row.expense_account
		for row in doc.get("account_budgets") or []
		if row.expense_account
	}


def validate_mapping_changes(doc, method=None):
	previous = doc.get_doc_before_save()
	before = _mapping_values(previous) if previous else {}
	after = _mapping_values(doc)
	legacy_before = _legacy_ledger_values(previous) if previous else {}
	legacy_after = _legacy_ledger_values(doc)
	changed = before != after or legacy_before != legacy_after
	if changed and not (_mapping.get() is not None and _mapping.get() == doc.name and can_map()):
		frappe.throw(
			_(
				"Ledger accounts are assigned separately in Home → Project account mapping by an Accounts Manager."
			),
			frappe.PermissionError,
		)


def label_has_claims(project, key):
	return bool(
		frappe.db.sql(
			"""SELECT d.name FROM `tabExpense Claim Detail` d
		JOIN `tabExpense Claim` c ON c.name=d.parent
		WHERE c.project=%s AND d.project_expense_account=%s AND c.docstatus!=2 LIMIT 1""",
			(project, key),
		)
	)


def resolve_budget_rows(doc, rows):
	"""Approval updates labels/allocations, retaining only server-held mappings."""
	existing = _legacy_ledger_values(doc)
	return [{**row, "expense_account": existing.get(row.get("budget_key"), "")} for row in rows]


def is_approved(project):
	return bool(frappe.db.exists("Project Proposal", {"project": project, "proposal_status": "Approved"}))


def _require_manager():
	if not can_map():
		frappe.throw(_("Only Accounts Managers may map expense labels to accounts."), frappe.PermissionError)


def _load(project):
	_require_manager()
	doc = frappe.get_doc("Project", project)
	if not is_approved(project) or not cint(doc.get("project_setup_version")):
		frappe.throw(_("A Projects Manager must approve this project before accounts can be mapped."))
	return doc


def _serialize(doc):
	suggestions = _mapping_values(doc)
	rows = [
		{
			"budget_key": row.budget_key,
			"employee_label": row.employee_label,
			"approved_amount": flt(row.approved_amount),
			"is_active": cint(row.is_active),
			"expense_accounts": suggestions.get(row.budget_key, []),
		}
		for row in doc.get("account_budgets") or []
	]
	return {
		"name": doc.name,
		"project_name": doc.project_name,
		"modified": str(doc.modified),
		"rows": rows,
		"ready": all(row["expense_accounts"] for row in rows if row["is_active"]),
		"closed": doc.get("budget_status") == "Closed" or bool(cint(doc.get("is_archived"))),
	}


@frappe.whitelist(methods=["POST"])
def get_mapping_workspace(project=None):
	_require_manager()
	if project:
		doc = _load(project)
		accounts = frappe.get_all(
			"Account",
			filters={"company": doc.company, "root_type": "Expense", "is_group": 0, "disabled": 0},
			fields=["name", "account_name"],
			order_by="account_name asc",
			limit_page_length=0,
		)
		return {"project": _serialize(doc), "accounts": accounts}
	approved = frappe.get_all("Project Proposal", filters={"proposal_status": "Approved"}, pluck="project")
	projects = frappe.get_all(
		"Project",
		filters={
			"name": ["in", list(set(filter(None, approved))) or [""]],
			"project_setup_version": [">", 0],
			"is_archived": 0,
		},
		pluck="name",
		order_by="modified desc",
	)
	return {"projects": [_serialize(frappe.get_doc("Project", name)) for name in projects]}


@frappe.whitelist(methods=["POST"])
def save_account_mapping(project, modified, mappings):
	doc = _load(project)
	frappe.db.sql("SELECT name FROM `tabProject` WHERE name=%s FOR UPDATE", project)
	doc.reload()
	if str(doc.modified) != modified:
		frappe.throw(
			_("The project changed. Reload before saving account mappings."), frappe.TimestampMismatchError
		)
	if doc.get("budget_status") == "Closed" or cint(doc.get("is_archived")):
		frappe.throw(_("Closed or archived projects cannot be mapped."))
	mappings = frappe.parse_json(mappings)
	if not isinstance(mappings, list) or len(mappings) > 100:
		frappe.throw(_("Invalid account mappings."))
	rows = {row.budget_key: row for row in doc.account_budgets}
	seen = set()
	before = _mapping_values(doc)
	from volunteering.volunteering.project_expense_accounts import _validate_account

	new_rows = []
	for mapping in mappings:
		if not isinstance(mapping, dict) or "budget_key" not in mapping:
			frappe.throw(_("Only label IDs and expense-account suggestions may be changed here."))
		if set(mapping) - {"budget_key", "expense_accounts", "expense_account"}:
			frappe.throw(_("Only label IDs and expense-account suggestions may be changed here."))
		key = mapping["budget_key"]
		accounts = mapping.get("expense_accounts")
		if accounts is None:  # compatibility with the former one-account client
			accounts = [mapping.get("expense_account")] if mapping.get("expense_account") else []
		if not isinstance(accounts, list) or len(accounts) > 25:
			frappe.throw(_("A label may have up to 25 suggested expense accounts."))
		if key not in rows or key in seen:
			frappe.throw(_("Unknown or duplicate project expense label."))
		seen.add(key)
		deduplicated = []
		for value in accounts:
			account = cstr(value).strip()
			if not account or account in deduplicated:
				continue
			_validate_account(account, doc.company)
			deduplicated.append(account)
			new_rows.append({"budget_key": key, "expense_account": account})
		# Preserve the old column as a first-suggestion mirror for reports and
		# older clients. It is not the final posting decision.
		rows[key].expense_account = deduplicated[0] if deduplicated else ""
	if seen != set(rows):
		frappe.throw(_("Include a row for every approved label when saving account suggestions."))
	doc.set("expense_account_mappings", new_rows)
	with mapping_context(doc.name):
		doc.save(ignore_permissions=True)
	after = _mapping_values(doc)
	if before != after:
		revision = frappe.get_doc(
			{
				"doctype": "Project Budget Revision",
				"project": doc.name,
				"changed_by": frappe.session.user,
				"changed_on": now_datetime(),
				"reason": "Expense label ledger mapping (Accounts Manager)",
				"before_values": json.dumps({"ledger_mappings": before}, sort_keys=True),
				"after_values": json.dumps({"ledger_mappings": after}, sort_keys=True),
			}
		)
		revision.flags.from_project_workspace = True
		revision.insert(ignore_permissions=True)
	return _serialize(doc)


def backfill_budget_labels():
	"""Idempotent additive upgrade; never change historical ledger postings."""
	if not frappe.db.has_column("Project Account Budget", "budget_key"):
		return
	by_project = {}
	for row in frappe.get_all(
		"Project Account Budget", fields=["name", "parent", "budget_key", "expense_account"]
	):
		key = row.budget_key or frappe.generate_hash(length=20)
		if not row.budget_key:
			frappe.db.set_value("Project Account Budget", row.name, "budget_key", key, update_modified=False)
		if row.expense_account:
			by_project.setdefault(row.parent, {}).setdefault(row.expense_account, []).append(key)
	for project, accounts in by_project.items():
		for account, keys in accounts.items():
			if len(keys) != 1:
				continue
			frappe.db.sql(
				"""UPDATE `tabExpense Claim Detail` d
				JOIN `tabExpense Claim` c ON c.name=d.parent
				SET d.project_expense_account=%s
				WHERE c.project=%s AND d.default_account=%s
				AND (IFNULL(d.project_expense_account, '')='' OR d.project_expense_account=%s)""",
				(keys[0], project, account, account),
			)
	# Keep old draft/change requests usable, but remove proposed ledger choices:
	# future approvals retain existing server mappings or await Accounts Manager.
	for proposal in frappe.get_all("Project Proposal", fields=["name", "project", "proposal_data"]):
		try:
			data = json.loads(proposal.proposal_data or "{}")
		except TypeError, ValueError:
			continue
		if not isinstance(data, dict):
			continue
		changed = False
		for row in data.get("account_budgets", []):
			if row.get("budget_key") and "expense_account" not in row:
				continue
			account = row.pop("expense_account", "")
			keys = by_project.get(proposal.project, {}).get(account, [])
			row["budget_key"] = row.get("budget_key") or (
				keys[0] if len(keys) == 1 else frappe.generate_hash(length=20)
			)
			changed = True
		if changed:
			frappe.db.set_value(
				"Project Proposal", proposal.name, "proposal_data", json.dumps(data), update_modified=False
			)
	# Existing technical field names are retained for database/API compatibility.
	for name, label in (
		("Project-account_budgets", "Expense Break Up"),
		("Project-account_budget_control", "Expense Category Budget Control"),
		("Expense Claim Detail-project_expense_account", "Project Expense Category"),
	):
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, "label", label, update_modified=False)
	frappe.clear_cache(doctype="Project")
	frappe.clear_cache(doctype="Expense Claim Detail")
