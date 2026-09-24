"""Accounts-Manager-only Chart of Accounts administration for Home."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

SEVAMRITA_COMPANY = "Sevamrita Foundation"
MANAGER_ROLE = "Accounts Manager"
EDITABLE_FIELDS = {
	"account_name",
	"account_number",
	"parent_account",
	"is_group",
	"account_type",
	"account_currency",
	"disabled",
	"tax_rate",
	"balance_must_be",
	"include_in_gross",
}


def can_manage(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or (user != "Guest" and MANAGER_ROLE in frappe.get_roles(user))


def _require_manager():
	if not can_manage():
		frappe.throw(
			_("Only Accounts Managers and Administrator may manage the Chart of Accounts."),
			frappe.PermissionError,
		)


def _require_company():
	if not frappe.db.exists("Company", SEVAMRITA_COMPANY):
		frappe.throw(_("Set up Sevamrita Foundation before managing its Chart of Accounts."))
	return SEVAMRITA_COMPANY


def _account_types():
	field = frappe.get_meta("Account").get_field("account_type")
	return [row.strip() for row in cstr(field.options).splitlines() if row.strip()]


def _serialize_accounts(company):
	rows = frappe.get_all(
		"Account",
		filters={"company": company},
		fields=[
			"name",
			"account_name",
			"account_number",
			"parent_account",
			"is_group",
			"root_type",
			"report_type",
			"account_type",
			"account_currency",
			"disabled",
			"tax_rate",
			"balance_must_be",
			"include_in_gross",
			"lft",
			"rgt",
			"modified",
		],
		order_by="lft asc",
		limit_page_length=0,
	)
	stack = []
	serialized = []
	for row in rows:
		while stack and cint(row.lft) > stack[-1]:
			stack.pop()
		depth = len(stack)
		stack.append(cint(row.rgt))
		serialized.append(
			{
				"name": row.name,
				"account_name": row.account_name,
				"account_number": row.account_number or "",
				"parent_account": row.parent_account or "",
				"is_group": cint(row.is_group),
				"is_root": not bool(row.parent_account),
				"root_type": row.root_type or "",
				"report_type": row.report_type or "",
				"account_type": row.account_type or "",
				"account_currency": row.account_currency or "",
				"disabled": cint(row.disabled),
				"tax_rate": flt(row.tax_rate),
				"balance_must_be": row.balance_must_be or "",
				"include_in_gross": cint(row.include_in_gross),
				"depth": depth,
				"has_children": cint(row.rgt) - cint(row.lft) > 1,
				"modified": str(row.modified),
			}
		)
	return serialized


def _workspace(saved_account=None):
	company = _require_company()
	accounts = _serialize_accounts(company)
	return {
		"company": company,
		"company_currency": frappe.db.get_value("Company", company, "default_currency") or "INR",
		"accounts": accounts,
		"parent_accounts": [
			{
				"name": row["name"],
				"label": row["account_name"],
				"root_type": row["root_type"],
				"disabled": row["disabled"],
			}
			for row in accounts
			if row["is_group"]
		],
		"account_types": _account_types(),
		"currencies": frappe.get_all(
			"Currency", filters={"enabled": 1}, pluck="name", order_by="name asc", limit_page_length=0
		),
		"saved_account": saved_account or "",
	}


def _parse_details(details):
	details = frappe.parse_json(details)
	if not isinstance(details, dict) or set(details) - EDITABLE_FIELDS:
		frappe.throw(_("Invalid account details."))
	name = cstr(details.get("account_name")).strip()
	parent = cstr(details.get("parent_account")).strip()
	if not name:
		frappe.throw(_("Account name is required."))
	if len(name) > 140:
		frappe.throw(_("Account name is too long."))
	if not parent:
		frappe.throw(_("Choose a parent group."))
	company = _require_company()
	parent_values = frappe.db.get_value(
		"Account", parent, ["company", "is_group", "disabled"], as_dict=True
	)
	if not parent_values or parent_values.company != company or not cint(parent_values.is_group):
		frappe.throw(_("Choose a group from Sevamrita Foundation's Chart of Accounts."))
	is_group = cint(details.get("is_group"))
	account_type = cstr(details.get("account_type")).strip()
	if is_group:
		account_type = ""
	elif account_type and account_type not in _account_types():
		frappe.throw(_("Choose a valid account type."))
	currency = cstr(details.get("account_currency")).strip()
	if is_group:
		currency = ""
	elif currency and not frappe.db.exists("Currency", {"name": currency, "enabled": 1}):
		frappe.throw(_("Choose an enabled currency."))
	balance_must_be = cstr(details.get("balance_must_be")).strip()
	if balance_must_be not in ("", "Debit", "Credit"):
		frappe.throw(_("Balance must be Debit, Credit or unrestricted."))
	return {
		"account_name": name,
		"account_number": cstr(details.get("account_number")).strip(),
		"parent_account": parent,
		"is_group": is_group,
		"account_type": account_type,
		"account_currency": currency,
		"disabled": cint(details.get("disabled")),
		"tax_rate": flt(details.get("tax_rate")) if account_type == "Tax" else 0,
		"balance_must_be": "" if is_group else balance_must_be,
		"include_in_gross": 0 if is_group else cint(details.get("include_in_gross")),
	}


@frappe.whitelist(methods=["POST"])
def get_chart_of_accounts():
	_require_manager()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def save_account(details, account=None, expected_modified=None):
	"""Create a child account, or safely update a non-root account."""
	_require_manager()
	values = _parse_details(details)
	company = _require_company()

	if not account:
		parent_disabled = frappe.db.get_value("Account", values["parent_account"], "disabled")
		if cint(parent_disabled):
			frappe.throw(_("A new account cannot be added below a disabled group."))
		doc = frappe.get_doc(
			{
				"doctype": "Account",
				"company": company,
				**values,
			}
		)
		doc.insert()
		return _workspace(doc.name)

	frappe.db.sql("SELECT name FROM `tabAccount` WHERE name=%s FOR UPDATE", account)
	doc = frappe.get_doc("Account", account)
	if doc.company != company:
		frappe.throw(_("This account is outside Sevamrita Foundation."), frappe.PermissionError)
	if not doc.parent_account:
		frappe.throw(_("Root accounts cannot be edited."))
	if expected_modified and str(doc.modified) != cstr(expected_modified):
		frappe.throw(_("The account changed. Reload it before saving."), frappe.TimestampMismatchError)
	if cint(doc.is_group) != values["is_group"]:
		frappe.throw(
			_("An existing account cannot change between Group and Ledger here. Create a new account instead.")
		)
	if values["parent_account"] == doc.name:
		frappe.throw(_("An account cannot be its own parent."))
	parent_bounds = frappe.db.get_value(
		"Account", values["parent_account"], ["lft", "rgt"], as_dict=True
	)
	if (
		cint(doc.is_group)
		and parent_bounds
		and cint(parent_bounds.lft) > cint(doc.lft)
		and cint(parent_bounds.rgt) < cint(doc.rgt)
	):
		frappe.throw(_("A group cannot be moved below one of its own children."))

	old_name = doc.name
	for field in (
		"parent_account",
		"account_type",
		"account_currency",
		"disabled",
		"tax_rate",
		"balance_must_be",
		"include_in_gross",
	):
		doc.set(field, values[field])
	doc.save()

	if values["account_name"] != doc.account_name or values["account_number"] != (doc.account_number or ""):
		from erpnext.accounts.doctype.account.account import update_account_number

		new_name = update_account_number(
			old_name,
			values["account_name"],
			values["account_number"] or None,
		)
		old_name = new_name or old_name
	frappe.clear_cache(doctype="Account")
	return _workspace(old_name)


@frappe.whitelist(methods=["POST"])
def delete_account(account, expected_modified=None):
	"""Delete only a non-root account; ERPNext blocks used accounts and non-empty groups."""
	_require_manager()
	company = _require_company()
	frappe.db.sql("SELECT name FROM `tabAccount` WHERE name=%s FOR UPDATE", account)
	doc = frappe.get_doc("Account", account)
	if doc.company != company:
		frappe.throw(_("This account is outside Sevamrita Foundation."), frappe.PermissionError)
	if not doc.parent_account:
		frappe.throw(_("Root accounts cannot be deleted."))
	if expected_modified and str(doc.modified) != cstr(expected_modified):
		frappe.throw(_("The account changed. Reload it before deleting."), frappe.TimestampMismatchError)
	frappe.delete_doc("Account", account)
	frappe.clear_cache(doctype="Account")
	return _workspace()
