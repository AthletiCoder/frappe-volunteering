"""Chart of Accounts administration and read-only ledgers for Home."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, nowdate

SEVAMRITA_COMPANY = "Sevamrita Foundation"
MANAGER_ROLE = "Accounts Manager"
READER_ROLES = frozenset({"Accounts Manager", "Accounts User"})
LEDGER_PAGE_SIZE = 50
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


def can_view_ledgers(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or (user != "Guest" and bool(READER_ROLES.intersection(frappe.get_roles(user))))


def _require_reader():
	if not can_view_ledgers():
		frappe.throw(
			_("Only Accounts Users, Accounts Managers and Administrator may view account ledgers."),
			frappe.PermissionError,
		)


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
	today = getdate(nowdate())
	fy_start_year = today.year if today.month >= 4 else today.year - 1
	return {
		"company": company,
		"company_currency": frappe.db.get_value("Company", company, "default_currency") or "INR",
		"can_manage": can_manage(),
		"default_from_date": f"{fy_start_year}-04-01",
		"default_to_date": today.isoformat(),
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
	_require_reader()
	return _workspace()


def _ledger_dates(from_date, to_date):
	try:
		start = getdate(from_date)
		end = getdate(to_date)
	except (TypeError, ValueError):
		frappe.throw(_("Choose valid From and To dates."))
	if not from_date or not to_date or start > end:
		frappe.throw(_("Choose a valid date range with From on or before To."))
	return start, end


@frappe.whitelist(methods=["POST"])
def get_account_ledger(account, from_date, to_date, page=1):
	"""A bounded, read-only statement for one Sevamrita posting account.

	Debit-positive balances are displayed as Dr; credit-positive as Cr. The
	opening amount includes every non-cancelled GL entry before the selected
	date range, so pagination never changes the statement's totals.
	"""
	_require_reader()
	company = _require_company()
	account = cstr(account).strip()
	details = frappe.db.get_value(
		"Account", {"name": account, "company": company},
		["name", "account_name", "account_number", "is_group", "root_type", "disabled"],
		as_dict=True,
	)
	if not details:
		frappe.throw(_("Choose a ledger in Sevamrita Foundation's Chart of Accounts."), frappe.PermissionError)
	if cint(details.is_group):
		frappe.throw(_("Choose a ledger account, not a group."))
	start, end = _ledger_dates(from_date, to_date)
	try:
		page = int(page)
	except (TypeError, ValueError):
		frappe.throw(_("Choose a valid page number."))
	if page < 1 or page > 10000:
		frappe.throw(_("Choose a valid page number."))

	base = {"company": company, "account": account, "start": start, "end": end}
	opening = frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) AS balance
		FROM `tabGL Entry`
		WHERE company = %(company)s AND account = %(account)s AND is_cancelled = 0
		AND posting_date < %(start)s""",
		base, as_dict=True,
	)[0].balance
	summary = frappe.db.sql(
		"""SELECT COUNT(*) AS entry_count, COALESCE(SUM(debit), 0) AS debit,
		COALESCE(SUM(credit), 0) AS credit
		FROM `tabGL Entry`
		WHERE company = %(company)s AND account = %(account)s AND is_cancelled = 0
		AND posting_date BETWEEN %(start)s AND %(end)s""",
		base, as_dict=True,
	)[0]
	rows = frappe.db.sql(
		"""SELECT name, posting_date, voucher_type, voucher_no, remarks, against,
		party_type, party, debit, credit, creation
		FROM `tabGL Entry`
		WHERE company = %(company)s AND account = %(account)s AND is_cancelled = 0
		AND posting_date BETWEEN %(start)s AND %(end)s
		ORDER BY posting_date ASC, creation ASC, name ASC
		LIMIT %(limit)s OFFSET %(offset)s""",
		{**base, "limit": LEDGER_PAGE_SIZE, "offset": (page - 1) * LEDGER_PAGE_SIZE},
		as_dict=True,
	)
	page_opening = flt(opening)
	if rows and page > 1:
		first = rows[0]
		page_opening += flt(frappe.db.sql(
			"""SELECT COALESCE(SUM(debit - credit), 0) AS balance
			FROM `tabGL Entry`
			WHERE company = %(company)s AND account = %(account)s AND is_cancelled = 0
			AND posting_date BETWEEN %(start)s AND %(end)s
			AND (posting_date < %(first_date)s
			OR (posting_date = %(first_date)s AND creation < %(first_creation)s)
			OR (posting_date = %(first_date)s AND creation = %(first_creation)s AND name < %(first_name)s))""",
			{**base, "first_date": first.posting_date, "first_creation": first.creation, "first_name": first.name},
			as_dict=True,
		)[0].balance)
	balance = page_opening
	entries = []
	for row in rows:
		balance += flt(row.debit) - flt(row.credit)
		entries.append({
			"name": row.name,
			"posting_date": str(row.posting_date),
			"voucher_type": row.voucher_type or "",
			"voucher_no": row.voucher_no or "",
			"remarks": row.remarks or "",
			"against": row.against or "",
			"party_type": row.party_type or "",
			"party": row.party or "",
			"debit": flt(row.debit),
			"credit": flt(row.credit),
			"balance": flt(balance),
		})
	return {
		"account": details,
		"currency": frappe.db.get_value("Company", company, "default_currency") or "INR",
		"from_date": start.isoformat(),
		"to_date": end.isoformat(),
		"opening_balance": flt(opening),
		"total_debit": flt(summary.debit),
		"total_credit": flt(summary.credit),
		"closing_balance": flt(opening) + flt(summary.debit) - flt(summary.credit),
		"entry_count": cint(summary.entry_count),
		"page": page,
		"page_size": LEDGER_PAGE_SIZE,
		"entries": entries,
	}


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
