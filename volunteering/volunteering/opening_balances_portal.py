"""Controlled, one-time opening balances from the Accounts Home workspace.

Each submitted amount is paired with Temporary Opening. This permits a bank
balance to be entered before the rest of the migration without pretending the
unexplained difference is a donation or a fund balance.
"""

from __future__ import annotations

import base64
import binascii
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

from volunteering.volunteering.chart_of_accounts_portal import (
	SEVAMRITA_COMPANY,
	can_manage,
)

MARKER = "Sevamrita Home opening balance:"
PARTY_TYPES = {"Receivable": {"Customer", "Employee"}, "Payable": {"Supplier", "Employee"}}
MAX_PROOF_FILES = 3
MAX_PROOF_BYTES = 5 * 1024 * 1024
PROOF_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx", "xlsx", "csv"}


def _require_manager():
	if not can_manage():
		frappe.throw(_("Only Accounts Managers and Administrator can record opening balances."), frappe.PermissionError)


def _company_currency():
	company = SEVAMRITA_COMPANY
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Set up Sevamrita Foundation before recording opening balances."))
	return frappe.db.get_value("Company", company, "default_currency") or "INR"


def _temporary_account(create=False):
	rows = frappe.get_all(
		"Account",
		filters={"company": SEVAMRITA_COMPANY, "account_type": "Temporary"},
		fields=["name", "is_group", "disabled"],
		limit_page_length=0,
	)
	if len(rows) > 1:
		frappe.throw(_("More than one Temporary account exists. Resolve this in the Chart of Accounts first."))
	if rows:
		if rows[0].is_group or rows[0].disabled:
			frappe.throw(_("The Temporary Opening account must be an active ledger account."))
		return rows[0].name
	if not create:
		return None
	root = frappe.db.get_value(
		"Account",
		{"company": SEVAMRITA_COMPANY, "root_type": "Liability", "parent_account": ["is", "not set"]},
		"name",
	)
	if not root:
		frappe.throw(_("A Liability root is required for the Temporary Opening account."))
	account = frappe.get_doc({
		"doctype": "Account",
		"company": SEVAMRITA_COMPANY,
		"account_name": "Temporary Opening",
		"parent_account": root,
		"is_group": 0,
		"account_type": "Temporary",
	})
	account.insert(ignore_permissions=True)
	return account.name


def _opening_date(raw):
	try:
		date = getdate(raw)
	except (TypeError, ValueError):
		frappe.throw(_("Enter a valid opening date."))
	if not date or date > getdate(nowdate()):
		frappe.throw(_("Opening date must not be in the future."))
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_year

	try:
		fiscal_year = get_fiscal_year(date, company=SEVAMRITA_COMPANY)
	except FiscalYearError:
		frappe.throw(_("Configure a Fiscal Year covering the opening date before posting."))
	if date != getdate(fiscal_year[1]):
		frappe.throw(_("Use the first day of the Fiscal Year for starting balances."))
	return date


def _amount(raw):
	try:
		value = Decimal(str(raw))
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw(_("Enter a valid opening amount."))
	if not value.is_finite() or value <= 0 or value > Decimal("999999999999.99") or value.as_tuple().exponent < -2:
		frappe.throw(_("Opening amount must be positive and have at most two decimal places."))
	return value


def _account_and_party(data, currency):
	account_name = cstr(data.get("account")).strip()
	account = frappe.db.get_value(
		"Account", account_name,
		["name", "company", "is_group", "disabled", "root_type", "account_type", "account_currency"],
		as_dict=True,
	)
	if not account or account.company != SEVAMRITA_COMPANY or account.is_group or account.disabled:
		frappe.throw(_("Choose an active Sevamrita ledger account."))
	if account.root_type not in {"Asset", "Liability", "Equity"} or account.account_type == "Temporary":
		frappe.throw(_("Opening balances here are for balance-sheet ledgers, not income, expenses or Temporary Opening."))
	if account.account_currency and account.account_currency != currency:
		frappe.throw(_("This screen currently supports only the company currency."))
	party_type = cstr(data.get("party_type")).strip()
	party = cstr(data.get("party")).strip()
	allowed = PARTY_TYPES.get(account.account_type)
	if allowed:
		if party_type not in allowed or not party or not frappe.db.exists(party_type, party):
			frappe.throw(_("Choose an existing party for this receivable or payable balance."))
	elif party_type or party:
		frappe.throw(_("A party may only be set for a Receivable or Payable ledger."))
	return account, party_type, party


def _existing_opening(account, party_type, party):
	filters = {"company": SEVAMRITA_COMPANY, "account": account, "is_opening": "Yes", "is_cancelled": 0}
	if party_type:
		filters.update({"party_type": party_type, "party": party})
	return frappe.db.exists("GL Entry", filters)


def _proof_documents(raw):
	if raw is None:
		return []
	if not isinstance(raw, list) or len(raw) > MAX_PROOF_FILES:
		frappe.throw(_("Attach no more than three proof documents."))
	documents = []
	for item in raw:
		if not isinstance(item, dict) or set(item) != {"file_name", "content"}:
			frappe.throw(_("Invalid opening-balance proof document."))
		name = PurePath(cstr(item["file_name"]).replace("\\", "/")).name
		extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
		encoded = item["content"]
		if not name or len(name) > 140 or extension not in PROOF_EXTENSIONS or not isinstance(encoded, str):
			frappe.throw(_("Attach a PDF, PNG, JPEG, DOCX, XLSX or CSV document."))
		if len(encoded) > ((MAX_PROOF_BYTES + 2) // 3) * 4:
			frappe.throw(_("Each proof document must be 5 MB or smaller."))
		try:
			content = base64.b64decode(encoded, validate=True)
		except (ValueError, binascii.Error):
			frappe.throw(_("An opening-balance proof document could not be read."))
		if not content or len(content) > MAX_PROOF_BYTES:
			frappe.throw(_("Each proof document must be 5 MB or smaller."))
		valid = (
			(extension == "pdf" and content.startswith(b"%PDF-"))
			or (extension == "png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
			or (extension in {"jpg", "jpeg"} and content.startswith(b"\xff\xd8\xff"))
		)
		if extension in {"docx", "xlsx"}:
			try:
				with ZipFile(BytesIO(content)) as archive:
					names = set(archive.namelist())
					valid = "[Content_Types].xml" in names and (
						"word/document.xml" in names if extension == "docx" else "xl/workbook.xml" in names
					)
			except BadZipFile:
				valid = False
		if extension == "csv":
			try:
				content.decode("utf-8-sig")
				valid = b"\x00" not in content
			except UnicodeDecodeError:
				valid = False
		if not valid:
			frappe.throw(_("The proof document does not match its file type."))
		documents.append((name, content))
	return documents


def _workspace():
	currency = _company_currency()
	temporary = _temporary_account()
	from erpnext.accounts.utils import get_fiscal_year

	fiscal_year = get_fiscal_year(nowdate(), company=SEVAMRITA_COMPANY)
	accounts = frappe.get_all(
		"Account",
		filters={"company": SEVAMRITA_COMPANY, "is_group": 0, "disabled": 0,
			"root_type": ["in", ["Asset", "Liability", "Equity"]]},
		fields=["name", "account_name", "account_number", "root_type", "account_type", "account_currency"],
		order_by="root_type asc, account_name asc", limit_page_length=0,
	)
	accounts = [row for row in accounts if row.account_type != "Temporary" and (not row.account_currency or row.account_currency == currency)]
	history = frappe.get_all(
		"Journal Entry",
		filters={"company": SEVAMRITA_COMPANY, "voucher_type": "Opening Entry", "docstatus": 1,
			"user_remark": ["like", f"{MARKER}%"]},
		fields=["name", "posting_date", "user_remark", "creation"],
		order_by="creation desc", limit_page_length=0,
	)
	for record in history:
		rows = frappe.get_all("Journal Entry Account", filters={"parent": record.name},
			fields=["account", "party_type", "party", "debit_in_account_currency", "credit_in_account_currency"],
			order_by="idx asc")
		record["rows"] = [row for row in rows if row.account != temporary]
		record["attachments"] = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Journal Entry", "attached_to_name": record.name, "is_private": 1},
			fields=["file_name", "file_url"],
			order_by="creation asc",
		)
	temporary_balance = 0
	if temporary:
		temporary_balance = frappe.db.sql(
			"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabGL Entry`
			WHERE company=%s AND account=%s AND is_cancelled=0""",
			(SEVAMRITA_COMPANY, temporary),
		)[0][0]
	return {
		"company": SEVAMRITA_COMPANY, "currency": currency,
		"today": nowdate(), "default_opening_date": str(fiscal_year[1]),
		"temporary_account": temporary, "temporary_balance": float(temporary_balance or 0),
		"accounts": accounts, "history": history,
	}


@frappe.whitelist(methods=["POST"])
def get_opening_balances():
	_require_manager()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def get_opening_parties(party_type):
	_require_manager()
	party_type = cstr(party_type).strip()
	labels = {"Employee": "employee_name", "Supplier": "supplier_name", "Customer": "customer_name"}
	if party_type not in labels:
		frappe.throw(_("Choose Employee, Supplier or Customer."))
	rows = frappe.get_all(party_type, fields=["name", labels[party_type]], order_by="name asc", limit_page_length=1000)
	return [{"value": row.name, "label": f"{row.get(labels[party_type]) or row.name} · {row.name}"} for row in rows]


@frappe.whitelist(methods=["POST"])
def record_opening_balance(details):
	"""Post one reviewed starting balance, paired with Temporary Opening."""
	_require_manager()
	data = frappe.parse_json(details)
	if not isinstance(data, dict) or set(data) - {"account", "opening_date", "side", "amount", "party_type", "party", "source_reference", "attachments"}:
		frappe.throw(_("Invalid opening balance details."))
	proof_documents = _proof_documents(data.get("attachments"))
	currency = _company_currency()
	date = _opening_date(data.get("opening_date"))
	amount = _amount(data.get("amount"))
	side = cstr(data.get("side")).strip()
	if side not in {"Debit", "Credit"}:
		frappe.throw(_("Choose whether this balance is a debit or credit."))
	account, party_type, party = _account_and_party(data, currency)
	source = cstr(data.get("source_reference")).strip()
	if not source or len(source) > 240:
		frappe.throw(_("Enter a source reference of up to 240 characters, such as a closing trial balance or bank statement."))

	# Lock the chosen ledger so two simultaneous requests cannot post its opening twice.
	frappe.db.sql("SELECT name FROM `tabAccount` WHERE name=%s FOR UPDATE", account.name)
	if _existing_opening(account.name, party_type, party):
		frappe.throw(_("An opening balance already exists for this account and party. Review the existing entry before posting another."))
	if frappe.db.exists("GL Entry", {"company": SEVAMRITA_COMPANY, "account": account.name,
			"posting_date": ["<", str(date)], "is_cancelled": 0}):
		frappe.throw(_("This account has older ledger entries. Reconcile those before adding a starting balance."))
	temporary = _temporary_account(create=True)
	je = frappe.new_doc("Journal Entry")
	je.company = SEVAMRITA_COMPANY
	je.voucher_type = "Opening Entry"
	je.is_opening = "Yes"
	je.posting_date = date
	je.user_remark = f"{MARKER} {source} (recorded by {frappe.session.user})"
	entry = {"account": account.name, "party_type": party_type or None, "party": party or None}
	entry["debit_in_account_currency" if side == "Debit" else "credit_in_account_currency"] = float(amount)
	je.append("accounts", entry)
	je.append("accounts", {"account": temporary,
		"credit_in_account_currency" if side == "Debit" else "debit_in_account_currency": float(amount)})
	je.insert(ignore_permissions=True)
	je.submit()
	if proof_documents:
		from frappe.utils.file_manager import save_file

		for filename, content in proof_documents:
			save_file(filename, content, "Journal Entry", je.name, is_private=1)
	return {"journal_entry": je.name, "workspace": _workspace()}
