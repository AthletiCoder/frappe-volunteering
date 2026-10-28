"""Home purchasing, using ERPNext's order, receipt, invoice and payment records."""

from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from html import escape
from uuid import UUID

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import cint, cstr, flt, getdate, nowdate, now_datetime

from volunteering.volunteering.approval_routing import (
	escalate_to_next_approver, get_approver_action_flags,
)
from volunteering.volunteering.authority import user_has_board_of_directors
from volunteering.volunteering.chart_of_accounts_portal import SEVAMRITA_COMPANY
from volunteering.volunteering.home_cutover import require_home_project
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import get_accounting_settings

KEY = "home_purchase_request_key"
TAX_BREAKUP = "home_purchase_tax_breakup"
TAX_COMPONENTS = ("cgst", "sgst", "igst", "other_tax")
ROUTE = "/volunteering/vendor-purchases"
WORKSPACE_VIEWS = ("requests", "approvals", "accounts")


def _user():
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Log in to open vendor purchases."), frappe.PermissionError)
	return frappe.session.user


def _accounts(manager=False):
	user = _user()
	return user == "Administrator" or bool(
		set(frappe.get_roles(user)) & ({"Accounts Manager"} if manager else {"Accounts Manager", "Accounts User"})
	)


def _require_accounts(manager=False):
	if not _accounts(manager):
		frappe.throw(_("Accounts access is required for this action."), frappe.PermissionError)


@contextmanager
def _accounting_context():
	"""Use standard ERP mappers after the endpoint authorizes the exact purchase."""
	actor = frappe.session.user
	session = deepcopy(frappe.local.session)
	try:
		frappe.set_user("Administrator")
		yield
	finally:
		frappe.set_user(actor)
		frappe.local.session.clear()
		frappe.local.session.update(session)
		if getattr(frappe.local, "session_obj", None):
			frappe.local.session_obj.data = frappe.local.session


@contextmanager
def _item_access(doc):
	"""ERP pricing validates Item read access; allow only this authorized PO's items."""
	items = [frappe.get_cached_doc("Item", row.item_code) for row in doc.items]
	previous = [(item, item.flags.ignore_permissions) for item in items]
	try:
		for item in items:
			item.flags.ignore_permissions = True
		yield
	finally:
		for item, value in previous:
			item.flags.ignore_permissions = value


def _data(raw, allowed):
	value = frappe.parse_json(raw) if isinstance(raw, str) else raw
	if not isinstance(value, dict) or set(value) - set(allowed):
		frappe.throw(_("The purchase details contain unsupported fields."))
	return value


def _key(raw):
	try:
		return str(UUID(cstr(raw)))
	except (ValueError, TypeError, AttributeError):
		frappe.throw(_("A valid request key is required. Reload the form."))


def _number(raw, label, zero=False):
	try:
		value = Decimal(str(raw))
	except (InvalidOperation, ValueError, TypeError):
		frappe.throw(_("Enter a valid {0}.").format(label))
	if not value.is_finite() or value < 0 or (not zero and value == 0) or value > Decimal("99999999999.99"):
		frappe.throw(_("Enter a positive {0}.").format(label))
	return float(value)


def _date(raw, label, future=False):
	if not raw:
		frappe.throw(_("{0} is required.").format(label))
	try:
		value = getdate(raw)
	except (ValueError, TypeError):
		frappe.throw(_("Enter a valid {0}.").format(label))
	if not future and value > getdate(nowdate()):
		frappe.throw(_("{0} cannot be in the future.").format(label))
	return value


def _has_legacy_taxes(doc):
	return bool(doc.get("taxes") or doc.get("taxes_and_charges"))


def _gross_prices(doc):
	"""No additional tax or recoverable GST for Home's inclusive quotations.

	In particular, do not let company defaults or Item Tax Templates silently
	add tax a second time. Legacy documents keep their existing tax treatment.
	"""
	doc.set("taxes", [])
	doc.taxes_and_charges = ""
	doc.flags.dont_auto_add_taxes = True
	doc.disable_rounded_total = 1


def _check_gross_total(doc):
	expected = flt(sum(flt(row.amount) for row in doc.items), 2)
	if _has_legacy_taxes(doc) or flt(doc.grand_total, 2) != expected:
		frappe.throw(_("Tax-inclusive prices must remain the final total. Additional tax cannot be added to this Home purchase."))


def _tax_money(raw, label):
	try:
		amount = Decimal(str(raw if raw not in (None, "") else 0))
	except (InvalidOperation, ValueError, TypeError):
		frappe.throw(_("Enter a valid {0} amount.").format(label))
	if not amount.is_finite() or amount < 0 or amount > Decimal("99999999999.99") or amount != amount.quantize(Decimal("0.01")):
		frappe.throw(_("{0} must be a non-negative amount with at most two decimal places.").format(label))
	return amount


def _make_tax_breakup(raw, invoice, actor):
	"""Reference amounts only: gross expense/stock valuation and payable stay intact."""
	if raw is None:
		return None
	if not isinstance(raw, list) or len(raw) != len(invoice.items):
		frappe.throw(_("Enter the optional tax breakup once for every bill item."))
	choices = {}
	for value in raw:
		row = _data(value, {"receipt_item", *TAX_COMPONENTS})
		ref = row.get("receipt_item")
		if not isinstance(ref, str) or not ref or ref in choices:
			frappe.throw(_("Do not repeat or omit a bill item in the tax breakup."))
		choices[ref] = {key: _tax_money(row.get(key), key.upper().replace("_", " ")) for key in TAX_COMPONENTS}
	if set(choices) != {row.pr_detail for row in invoice.items}:
		frappe.throw(_("The tax breakup must belong to the selected delivery's bill items."))
	rows = []
	for item in invoice.items:
		components = choices[item.pr_detail]
		gross = Decimal(str(flt(item.amount, 2)))
		total_tax = sum(components.values(), Decimal(0))
		if total_tax > gross:
			frappe.throw(_("Included taxes cannot exceed the tax-inclusive amount for {0}.").format(item.item_name))
		if components["igst"] and (components["cgst"] or components["sgst"]):
			frappe.throw(_("Use either IGST or CGST/SGST for one bill item, not both."))
		rows.append({
			"receipt_item": item.pr_detail, "item_code": item.item_code, "item_name": item.item_name,
			"gross_amount": float(gross), "base_amount": float(gross - total_tax),
			"total_tax": float(total_tax), **{key: float(value) for key, value in components.items()},
		})
	return {
		"version": 1, "treatment": "Non-recoverable tax included in purchase cost",
		"currency": invoice.currency, "gross_total": flt(invoice.grand_total, 2),
		"base_total": flt(sum(row["base_amount"] for row in rows), 2),
		"tax_total": flt(sum(row["total_tax"] for row in rows), 2),
		"recorded_by": actor, "recorded_on": cstr(now_datetime()), "items": rows,
	}


def _employee():
	return frappe.db.get_value("Employee", {"user_id": _user(), "status": "Active"}, "name")


def _is_member(project, user):
	return any(row.user == user for row in project.project_participants)


def _project(name):
	require_home_project(name)
	project = frappe.get_doc("Project", name)
	if project.company != SEVAMRITA_COMPANY or project.operational_status != "Active" or project.budget_status == "Closed" or project.is_archived:
		frappe.throw(_("Choose an active approved project with open finances."))
	if not _accounts() and not _is_member(project, _user()):
		frappe.throw(_("You must belong to the selected project."), frappe.PermissionError)
	return project


def _order(name, modified=None, lock=False):
	_user()
	if lock:
		frappe.db.sql("SELECT name FROM `tabPurchase Order` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Purchase Order", name)
	if doc.company != SEVAMRITA_COMPANY or not doc.get(KEY):
		frappe.throw(_("This purchase is not available in Home."), frappe.PermissionError)
	require_home_project(doc.project)
	if not (_accounts() or doc.owner == _user() or doc.pending_approver == _user()):
		frappe.throw(_("You do not have access to this purchase."), frappe.PermissionError)
	if modified and cstr(doc.modified) != cstr(modified):
		frappe.throw(_("This purchase changed. Reload it before continuing."), frappe.TimestampMismatchError)
	return doc


def _workspace_view(view):
	view = cstr(view or "requests")
	if view not in WORKSPACE_VIEWS:
		frappe.throw(_("Choose My purchase requests, Purchase approvals or Approved purchases — Accounts."))
	if view == "accounts":
		_require_accounts()
	elif _user() != "Administrator" and not _employee():
		frappe.throw(_("An active employee account is required."), frappe.PermissionError)
	return view


def _authorize_workspace_order(doc, view):
	view = _workspace_view(view)
	if view == "requests" and doc.owner != _user():
		frappe.throw(_("My purchase requests shows only purchases you raised."), frappe.PermissionError)
	if view == "approvals" and (doc.pending_approver != _user() or doc.owner == _user() or doc.workflow_state != "Pending Approval" or doc.docstatus != 0):
		frappe.throw(_("Purchase approvals shows only pending requests assigned to you."), frappe.PermissionError)
	if view == "accounts" and (doc.docstatus != 1 or doc.workflow_state != "Approved"):
		frappe.throw(_("Only approved purchase orders are available for Accounts processing."), frappe.PermissionError)
	return view


def _approved(doc):
	if doc.docstatus != 1 or doc.workflow_state != "Approved" or doc.status in ("Closed", "Cancelled", "On Hold"):
		frappe.throw(_("This action requires an approved, open Purchase Order."))


def _audit(doc, action, actor):
	doc.add_comment("Comment", _("Home purchase: {0}; recorded by {1}.").format(action, actor))


def _setup():
	company = frappe.get_cached_doc("Company", SEVAMRITA_COMPANY)
	advance = company.default_advance_paid_account
	valid = advance and frappe.db.exists("Account", {
		"name": advance, "company": company.name, "root_type": "Asset", "account_type": "Receivable",
		"is_group": 0, "disabled": 0, "account_currency": company.default_currency,
	})
	return {
		"ready": bool(company.book_advance_payments_in_separate_party_account and valid),
		"advance_account": advance or "", "can_configure": _accounts(manager=True),
	}


@frappe.whitelist(methods=["POST"])
def configure_vendor_advances():
	"""Explicit Accounts Manager setup; preserve any already configured advance ledger."""
	_require_accounts(manager=True)
	company = frappe.get_doc("Company", SEVAMRITA_COMPANY)
	if not company.default_advance_paid_account:
		account = frappe.db.get_value("Account", {"company": company.name, "account_name": "Vendor Advances"}, "name")
		if account:
			doc = frappe.get_doc("Account", account)
			if doc.root_type != "Asset" or doc.is_group or doc.disabled:
				frappe.throw(_("Review the Vendor Advances account in Chart of Accounts first."))
			if doc.account_type != "Receivable":
				if doc.account_type or frappe.db.exists("GL Entry", {"account": account}):
					frappe.throw(_("The existing Vendor Advances ledger cannot be changed automatically."))
				doc.account_type = "Receivable"
				doc.save(ignore_permissions=True)
		else:
			parent = frappe.db.get_value("Account", {"company": company.name, "account_name": "Current Assets", "is_group": 1}, "name")
			parent = parent or frappe.db.get_value("Account", {"company": company.name, "root_type": "Asset", "parent_account": ["is", "not set"]}, "name")
			account = frappe.get_doc({"doctype": "Account", "company": company.name, "account_name": "Vendor Advances", "parent_account": parent, "account_type": "Receivable", "account_currency": company.default_currency}).insert(ignore_permissions=True).name
		company.default_advance_paid_account = account
	account = frappe.get_doc("Account", company.default_advance_paid_account)
	if account.root_type != "Asset" or account.account_type != "Receivable" or account.is_group or account.disabled:
		frappe.throw(_("Configure an active Asset / Receivable supplier advance account first."))
	company.book_advance_payments_in_separate_party_account = 1
	company.save(ignore_permissions=True)
	_audit(company, "enabled separate supplier advance accounting", _user())
	return _setup()


@frappe.whitelist(methods=["POST"])
def get_purchase_workspace(view="requests"):
	view = _workspace_view(view)
	finance = view == "accounts"
	filters = {"company": SEVAMRITA_COMPANY, KEY: ["is", "set"], "docstatus": ["!=", 2]}
	if view == "requests":
		filters["owner"] = _user()
	elif view == "approvals":
		filters.update({"pending_approver": _user(), "workflow_state": "Pending Approval", "docstatus": 0, "owner": ["!=", _user()]})
	else:
		filters.update({"workflow_state": "Approved", "docstatus": 1})
	from volunteering.volunteering.home_cutover import home_project_filter
	filters.update(home_project_filter())
	orders = frappe.get_all("Purchase Order", filters=filters,
		fields=["name", "supplier_name", "project", "workflow_state", "grand_total", "currency", "transaction_date", "status", "per_received", "per_billed", "advance_paid", "owner", "pending_approver"], order_by="modified desc", limit_page_length=200)
	from volunteering.volunteering.home_cutover import is_home_project
	orders = [row for row in orders if is_home_project(row.project)]
	links = frappe.get_all("Purchase Invoice Item", filters={"purchase_order": ["in", [row.name for row in orders]], "docstatus": 1}, fields=["parent", "purchase_order"], limit_page_length=0) if orders else []
	balances = {row.name: flt(row.outstanding_amount) for row in frappe.get_all("Purchase Invoice", filters={"name": ["in", list({link.parent for link in links})]}, fields=["name", "outstanding_amount"], limit_page_length=0)} if links else {}
	for order in orders:
		order.outstanding_amount = sum(balances.get(invoice, 0) for invoice in {link.parent for link in links if link.purchase_order == order.name})
	projects = []
	for row in frappe.get_all("Project", filters={"company": SEVAMRITA_COMPANY, "project_setup_version": [">", 0], "operational_status": "Active", "budget_status": ["!=", "Closed"], "is_archived": 0}, fields=["name", "project_name"]):
		if view == "requests" and (_accounts() or _is_member(frappe.get_doc("Project", row.name), _user())):
			projects.append({"value": row.name, "label": row.project_name})
	return {
		"view": view, "today": nowdate(), "currency": frappe.get_cached_value("Company", SEVAMRITA_COMPANY, "default_currency"),
		"orders": orders, "projects": projects,
		"suppliers": frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name", "supplier_name"], order_by="supplier_name", limit_page_length=500),
		"items": frappe.get_all("Item", filters={"disabled": 0, "is_purchase_item": 1, "is_fixed_asset": 0, "has_serial_no": 0, "has_batch_no": 0}, fields=["name", "item_name", "stock_uom", "is_stock_item"], order_by="item_name", limit_page_length=500),
		"warehouses": frappe.get_all("Warehouse", filters={"company": SEVAMRITA_COMPANY, "is_group": 0, "disabled": 0}, fields=["name", "warehouse_name"], limit_page_length=0),
		"expense_accounts": frappe.get_all("Account", filters={"company": SEVAMRITA_COMPANY, "root_type": "Expense", "is_group": 0, "disabled": 0}, fields=["name", "account_name"], order_by="account_name", limit_page_length=0) if finance else [],
		"payment_accounts": frappe.get_all("Account", filters={"company": SEVAMRITA_COMPANY, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0, "disabled": 0}, fields=["name", "account_name", "account_type", "account_currency"], limit_page_length=0) if finance else [],
		"modes": frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name", "type"], limit_page_length=200) if finance else [],
		"uoms": frappe.get_all("UOM", filters={"enabled": 1}, pluck="name", order_by="name", limit_page_length=0) if finance and _accounts(manager=True) else [],
		"capabilities": {"accounts": finance, "manage_suppliers": finance and _accounts(manager=True), "create": view == "requests" and not user_has_board_of_directors(_user())},
		"advance_setup": _setup() if finance else None,
		"cash_payment_limit": flt(get_accounting_settings().get("cash_payment_limit") or 2000) if finance else None,
	}


def _evidence(doctype, name, proof):
	from volunteering.volunteering.opening_balances_portal import _proof_documents
	from frappe.utils.file_manager import save_file
	for filename, content in _proof_documents([proof] if proof else []):
		save_file(filename, content, doctype, name, is_private=1)


def _files(doctype, names):
	if not names:
		return []
	return frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": ["in", names], "is_folder": 0}, fields=["file_name", "file_url", "attached_to_name"], limit_page_length=0)


def _share_with_requester(doc, user):
	if user and user != "Administrator":
		frappe.share.add(doc.doctype, doc.name, user=user, read=1, flags={"ignore_share_permission": True}, notify=0)


@contextmanager
def _party_account_access(doc):
	"""Allow ERP's currency check on the exact control account for this call.

	Any temporary share is removed before the request transaction commits.
	A later request, including a ledger-balance RPC, gains no account access.
	"""
	user = _user()
	with _accounting_context():
		from erpnext.accounts.party import get_party_account
		account = get_party_account("Supplier", doc.supplier, doc.company)
	created = None
	if account and user != "Administrator" and not frappe.db.exists("DocShare", {"share_doctype": "Account", "share_name": account, "user": user}):
		created = frappe.share.add("Account", account, user=user, read=1, notify=0, flags={"ignore_share_permission": True}).name
	try:
		yield
	finally:
		if created:
			frappe.delete_doc("DocShare", created, ignore_permissions=True, force=True, flags={"ignore_share_permission": True})


@frappe.whitelist(methods=["POST"])
def get_purchase(name, view=None):
	doc = _order(name)
	if view is not None:
		view = _authorize_workspace_order(doc, view)
	# Omitted view preserves the exact-document internal API used by workflow
	# mutations; every Home page explicitly supplies its own perspective.
	finance = _accounts() and view in (None, "accounts")
	receipt_names = frappe.get_all("Purchase Receipt Item", filters={"purchase_order": name, "docstatus": 1}, pluck="parent", distinct=True)
	invoice_names = frappe.get_all("Purchase Invoice Item", filters={"purchase_order": name, "docstatus": 1}, pluck="parent", distinct=True)
	receipts = frappe.get_all("Purchase Receipt", filters={"name": ["in", receipt_names]}, fields=["name", "posting_date", "grand_total"], order_by="posting_date", limit_page_length=0) if receipt_names else []
	invoices = frappe.get_all("Purchase Invoice", filters={"name": ["in", invoice_names]}, fields=["name", "bill_no", "bill_date", "posting_date", "grand_total", "total_advance", "outstanding_amount", "status"], order_by="posting_date", limit_page_length=0) if invoice_names else []
	if finance:
		for invoice in invoices:
			invoice["tax_breakup"] = frappe.parse_json(frappe.db.get_value("Purchase Invoice", invoice.name, TAX_BREAKUP) or "null")
	refs = frappe.get_all("Payment Entry Reference", filters={"reference_name": ["in", [name, *invoice_names]], "reference_doctype": ["in", ["Purchase Order", "Purchase Invoice"]], "docstatus": 1}, pluck="parent", distinct=True)
	# ERPNext reconciles an advance's PO reference into an invoice reference.
	payments = frappe.get_all("Payment Entry", filters={"name": ["in", refs]}, fields=["name", "posting_date", "paid_amount", "reference_no", "reference_date", "paid_from", "paid_to"], order_by="posting_date", limit_page_length=0) if refs else []
	editable = view in (None, "requests") and doc.docstatus == 0 and doc.workflow_state in ("Draft", "Rejected") and doc.owner == _user()
	reviewable = view in (None, "approvals") and doc.pending_approver == _user() and doc.owner != _user() and doc.workflow_state == "Pending Approval"
	transitions = []
	if editable or reviewable:
		doc.flags.ignore_permissions = True
		transitions = [row.action for row in get_transitions(doc)]
	flags = get_approver_action_flags("Purchase Order", name) if reviewable else {}
	if not flags.get("can_approve"):
		transitions = [action for action in transitions if action != "Approve"]
	items = [{key: row.get(key) for key in ("name", "item_code", "item_name", "description", "qty", "uom", "stock_uom", "rate", "amount", "received_qty", "billed_amt", "warehouse", "expense_account")} for row in doc.items]
	for receipt in receipts:
		receipt["items"] = frappe.get_all("Purchase Receipt Item", filters={"parent": receipt.name}, fields=["name", "purchase_order_item", "item_code", "item_name", "qty", "billed_amt", "amount", "rate", "expense_account"], limit_page_length=0)
	open_for_processing = doc.docstatus == 1 and doc.status not in ("Closed", "Cancelled", "On Hold")
	return {
		"name": doc.name, "modified": cstr(doc.modified), "supplier": doc.supplier, "supplier_name": doc.supplier_name,
		"project": doc.project, "project_name": frappe.db.get_value("Project", doc.project, "project_name"),
		"owner": doc.owner, "pending_approver": doc.pending_approver, "workflow_state": doc.workflow_state,
		"docstatus": doc.docstatus, "status": doc.status, "transaction_date": doc.transaction_date,
		"schedule_date": doc.schedule_date, "terms": doc.terms, "taxes_and_charges": doc.taxes_and_charges,
		"currency": doc.currency, "net_total": doc.net_total, "tax_amount": doc.total_taxes_and_charges,
		"prices_include_tax": not _has_legacy_taxes(doc),
		"grand_total": doc.grand_total, "advance_paid": doc.advance_paid,
		"items": items, "receipts": receipts, "invoices": invoices, "payments": payments,
		"attachments": [*_files("Purchase Order", [name]), *_files("Purchase Receipt", receipt_names), *_files("Purchase Invoice", invoice_names)],
		"actions": {"edit": editable, "review": reviewable, "transitions": transitions, "approval_flags": flags, "receive": open_for_processing and flt(doc.per_received) < 100 and (finance or (view in (None, "requests") and doc.owner == _user())), "invoice": open_for_processing and bool(receipts) and finance and flt(doc.per_billed) < 100, "pay": open_for_processing and finance},
	}


@frappe.whitelist(methods=["POST"])
def save_purchase(details, name=None, modified=None, submit=0):
	data = _data(details, {"request_key", "supplier", "project", "transaction_date", "schedule_date", "terms", "items", "taxes_and_charges", "proof"})
	if _user() != "Administrator" and not _employee():
		frappe.throw(_("An active employee account is required."), frappe.PermissionError)
	project = _project(data.get("project"))
	if not frappe.db.exists("Supplier", {"name": data.get("supplier"), "disabled": 0}):
		frappe.throw(_("Choose an enabled supplier."))
	if name:
		doc = _order(name, modified, lock=True)
		if doc.owner != _user() or doc.docstatus != 0 or doc.workflow_state not in ("Draft", "Rejected"):
			frappe.throw(_("Only the requester can edit an editable purchase draft."), frappe.PermissionError)
	else:
		key = _key(data.get("request_key"))
		existing = frappe.db.get_value("Purchase Order", {KEY: key}, "name")
		if existing:
			return get_purchase(existing)
		doc = frappe.new_doc("Purchase Order")
		doc.update({"company": SEVAMRITA_COMPANY, KEY: key, "owner": _user(), "currency": frappe.get_cached_value("Company", SEVAMRITA_COMPANY, "default_currency"), "conversion_rate": 1})
	doc.supplier = data["supplier"]
	with _accounting_context():
		from erpnext.accounts.party import get_party_account_currency
		doc.party_account_currency = get_party_account_currency("Supplier", doc.supplier, doc.company)
	if doc.party_account_currency != doc.currency:
		frappe.throw(_("Home purchasing currently requires the supplier ledger in the company currency."))
	doc.project = project.name
	doc.transaction_date = _date(data.get("transaction_date"), "Order date")
	doc.schedule_date = _date(data.get("schedule_date"), "Expected delivery date", future=True)
	if doc.schedule_date < doc.transaction_date:
		frappe.throw(_("Expected delivery cannot be before the order date."))
	doc.terms = escape(cstr(data.get("terms")).strip())
	# Retain historical tax rows, but new clients cannot choose or alter a
	# template (even by sending a forged employee request).
	if data.get("taxes_and_charges") and data["taxes_and_charges"] != doc.get("taxes_and_charges"):
		frappe.throw(_("Enter the supplier's tax-inclusive prices. Tax templates cannot be selected in Home purchase orders."), frappe.PermissionError)
	gross_prices = not _has_legacy_taxes(doc)
	if gross_prices:
		_gross_prices(doc)
	rows = data.get("items")
	if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
		frappe.throw(_("Add between one and fifty purchase items."))
	doc.set("items", [])
	for raw in rows:
		row = _data(raw, {"item_code", "description", "qty", "rate", "warehouse", "expense_account"})
		item = frappe.get_doc("Item", row.get("item_code"))
		if item.disabled or not item.is_purchase_item or item.is_fixed_asset or item.has_serial_no or item.has_batch_no:
			frappe.throw(_("Choose a purchase item without asset, serial or batch tracking."))
		warehouse = row.get("warehouse") or ""
		if item.is_stock_item and not frappe.db.exists("Warehouse", {"name": warehouse, "company": doc.company, "is_group": 0, "disabled": 0}):
			frappe.throw(_("Choose a Sevamrita warehouse for stock items."))
		account = row.get("expense_account") if _accounts() else None
		if account:
			_validate_expense_account(account)
		doc.append("items", {"item_code": item.name, "item_name": item.item_name, "description": escape(cstr(row.get("description") or item.item_name)), "qty": _number(row.get("qty"), "quantity"), "rate": _number(row.get("rate"), "rate"), "uom": item.stock_uom, "stock_uom": item.stock_uom, "conversion_factor": 1, "schedule_date": doc.schedule_date, "warehouse": warehouse, "expense_account": account, "project": doc.project, "cost_center": project.cost_center})
	doc.flags.authorized_home_purchase_creator = bool(_accounts())
	with _party_account_access(doc), _item_access(doc):
		doc.save(ignore_permissions=True)
	if gross_prices:
		_check_gross_total(doc)
	_share_with_requester(doc, doc.owner)
	_share_with_requester(doc, doc.pending_approver)
	_evidence(doc.doctype, doc.name, data.get("proof"))
	if cint(submit):
		with _party_account_access(doc), _item_access(doc):
			apply_workflow(doc, "Re-submit" if doc.workflow_state == "Rejected" else "Submit")
		if gross_prices:
			_check_gross_total(doc)
	return get_purchase(doc.name)


@frappe.whitelist(methods=["POST"])
def review_purchase(name, action, modified, reason=""):
	doc = _order(name, modified, lock=True)
	if not _has_legacy_taxes(doc):
		_gross_prices(doc)
	if doc.pending_approver != _user() or doc.workflow_state != "Pending Approval":
		frappe.throw(_("Only the assigned purchase approver can review this order."), frappe.PermissionError)
	if action not in ("Approve", "Reject", "Escalate"):
		frappe.throw(_("Choose a valid purchase decision."))
	if action != "Approve" and not cstr(reason).strip():
		frappe.throw(_("Enter a review note."))
	if action == "Escalate":
		if not get_approver_action_flags("Purchase Order", name).get("can_escalate"):
			frappe.throw(_("Your current authority covers this order. Approve or reject it."))
		doc.escalation_reason = cstr(reason).strip()
		escalate_to_next_approver(doc)
		with _party_account_access(doc), _item_access(doc):
			doc.save(ignore_permissions=True)
		_share_with_requester(doc, doc.pending_approver)
	else:
		if action == "Approve" and not get_approver_action_flags("Purchase Order", name).get("can_approve"):
			frappe.throw(_("This amount requires approval from a higher authority."), frappe.PermissionError)
		doc.flags.ignore_permissions = True
		with _party_account_access(doc), _item_access(doc):
			apply_workflow(doc, action)
	_audit(doc, f"{action}: {cstr(reason).strip()}", _user())
	if action == "Escalate":
		return {"redirect_to_list": True}
	return get_purchase(name)


def _duplicate(doctype, key, order):
	name = frappe.db.get_value(doctype, {KEY: key}, "name")
	if name:
		# Never return another order's document for a reused client token.
		field = {"Purchase Receipt": "purchase_order", "Purchase Invoice": "purchase_order"}.get(doctype)
		if field and not frappe.db.exists(doctype + " Item", {"parent": name, field: order.name}):
			frappe.throw(_("This request key was already used for another purchase."))
		return name


@frappe.whitelist(methods=["POST"])
def record_goods_received(name, details):
	doc = _order(name, lock=True)
	_approved(doc)
	if not (_accounts() or doc.owner == _user()):
		frappe.throw(_("Only the requester or Accounts can record delivery."), frappe.PermissionError)
	data = _data(details, {"request_key", "posting_date", "delivery_note", "items", "proof"})
	key = _key(data.get("request_key"))
	if _duplicate("Purchase Receipt", key, doc):
		return get_purchase(name)
	posting = _date(data.get("posting_date"), "Goods received date")
	if not isinstance(data.get("items"), list) or not data["items"]:
		frappe.throw(_("Enter the quantities received."))
	quantities = {}
	for row in data["items"]:
		row = _data(row, {"order_item", "qty"})
		if row.get("order_item") in quantities:
			frappe.throw(_("Do not repeat an order item."))
		quantities[row.get("order_item")] = _number(row.get("qty"), "received quantity", zero=True)
	known = {row.name: row for row in doc.items}
	if set(quantities) - set(known):
		frappe.throw(_("The delivery contains items outside this order."))
	for item, qty in quantities.items():
		if qty > flt(known[item].qty) - flt(known[item].received_qty) + 0.00001:
			frappe.throw(_("Received quantity exceeds the remaining order quantity."))
	if not any(quantities.values()):
		frappe.throw(_("Enter at least one received quantity greater than zero."))
	actor = _user()
	with _accounting_context():
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
		receipt = make_purchase_receipt(doc.name)
		if not _has_legacy_taxes(doc):
			_gross_prices(receipt)
		receipt.set("items", [row for row in receipt.items if quantities.get(row.purchase_order_item, 0) > 0])
		for row in receipt.items:
			row.qty = quantities[row.purchase_order_item]
		receipt.posting_date = posting
		receipt.set_posting_time = 1
		receipt.supplier_delivery_note = cstr(data.get("delivery_note")).strip()[:140]
		receipt.set(KEY, key)
		receipt.owner = actor
		receipt.insert()
		_share_with_requester(receipt, doc.owner)
		_evidence(receipt.doctype, receipt.name, data.get("proof"))
		receipt.submit()
		if not _has_legacy_taxes(doc):
			_check_gross_total(receipt)
		_audit(receipt, "goods received", actor)
	return get_purchase(name)


def _validate_expense_account(name):
	if not frappe.db.exists("Account", {"name": name, "company": SEVAMRITA_COMPANY, "root_type": "Expense", "is_group": 0, "disabled": 0}):
		frappe.throw(_("Select an active expense ledger for each invoice item."))


@frappe.whitelist(methods=["POST"])
def record_supplier_invoice(name, details):
	_require_accounts()
	doc = _order(name, lock=True)
	_approved(doc)
	data = _data(details, {"request_key", "receipt", "bill_no", "bill_date", "due_date", "items", "proof", "tax_breakup"})
	key = _key(data.get("request_key"))
	if _duplicate("Purchase Invoice", key, doc):
		return get_purchase(name)
	receipt = frappe.get_doc("Purchase Receipt", data.get("receipt"))
	if receipt.docstatus != 1 or receipt.is_return or receipt.company != doc.company or receipt.supplier != doc.supplier or any(row.purchase_order != doc.name for row in receipt.items):
		frappe.throw(_("Choose a submitted goods receipt belonging to this purchase."))
	bill_no = cstr(data.get("bill_no")).strip()
	if not bill_no or len(bill_no) > 140 or not data.get("proof"):
		frappe.throw(_("Enter the supplier invoice number and attach its bill."))
	frappe.db.sql("SELECT name FROM `tabSupplier` WHERE name=%s FOR UPDATE", doc.supplier)
	if frappe.db.exists("Purchase Invoice", {"supplier": doc.supplier, "company": doc.company, "bill_no": bill_no, "docstatus": ["!=", 2]}):
		frappe.throw(_("This supplier invoice number has already been recorded."))
	bill_date = _date(data.get("bill_date"), "Invoice date")
	due = _date(data.get("due_date") or bill_date, "Payment due date", future=True)
	if due < bill_date:
		frappe.throw(_("Payment due date cannot be before the invoice date."))
	rows = data.get("items")
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("Classify the invoice items."))
	choices = {}
	for raw in rows:
		row = _data(raw, {"receipt_item", "expense_account"})
		if row.get("receipt_item") in choices:
			frappe.throw(_("Do not repeat an invoice item."))
		_validate_expense_account(row.get("expense_account"))
		choices[row["receipt_item"]] = row["expense_account"]
	actor = _user()
	with _accounting_context():
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
		invoice = make_purchase_invoice(receipt.name)
		if not invoice or not invoice.items:
			frappe.throw(_("This delivery has already been fully invoiced."))
		if {row.pr_detail for row in invoice.items} != set(choices):
			frappe.throw(_("Classify every unbilled item from the selected delivery."))
		gross_prices = not _has_legacy_taxes(doc)
		if gross_prices:
			_gross_prices(invoice)
		elif data.get("tax_breakup") is not None:
			frappe.throw(_("This older order already has ERP tax rows. Keep its existing tax treatment instead of adding a second tax breakup."))
		invoice.project = doc.project
		invoice.bill_no = bill_no
		invoice.bill_date = bill_date
		invoice.posting_date = bill_date
		invoice.set_posting_time = 1
		invoice.due_date = due
		invoice.disable_rounded_total = 1
		invoice.set(KEY, key)
		invoice.owner = actor
		invoice.allocate_advances_automatically = 0
		invoice.only_include_allocated_payments = 1
		for row in invoice.items:
			row.expense_account = choices[row.pr_detail]
		invoice.set_missing_values()
		invoice.calculate_taxes_and_totals()
		if gross_prices:
			_check_gross_total(invoice)
		# Record the actual Accounts actor, not the scoped mapping Administrator.
		breakup = _make_tax_breakup(data.get("tax_breakup"), invoice, actor)
		invoice.set(TAX_BREAKUP, frappe.as_json(breakup) if breakup else None)
		invoice.set_advances()
		# Retain only advances paid for this order, even for repeat suppliers.
		allowed_payments = set(frappe.get_all("Payment Entry Reference", filters={"reference_doctype": "Purchase Order", "reference_name": doc.name, "docstatus": 1}, pluck="parent"))
		invoice.set("advances", [row for row in invoice.advances if row.reference_type == "Payment Entry" and row.reference_name in allowed_payments])
		invoice.insert()
		_share_with_requester(invoice, doc.owner)
		_evidence(invoice.doctype, invoice.name, data["proof"])
		workflow = frappe.db.get_value("Workflow", {"document_type": "Purchase Invoice", "is_active": 1}, "name")
		if workflow:
			transitions = get_transitions(invoice)
			immediate = [row for row in transitions if row.next_state == "Approved"]
			if len(immediate) != 1:
				frappe.throw(_("The configured invoice workflow needs a separate review. It cannot be posted from this purchase screen."))
			invoice = apply_workflow(invoice, immediate[0].action)
		else:
			invoice.submit()
		if gross_prices:
			_check_gross_total(invoice)
		_audit(invoice, "supplier bill posted; order advances applied", actor)
	return get_purchase(name)


@frappe.whitelist(methods=["POST"])
def record_vendor_payment(name, details):
	_require_accounts()
	doc = _order(name, lock=True)
	_approved(doc)
	data = _data(details, {"request_key", "invoice", "amount", "paid_from", "posting_date", "reference_no", "reference_date", "mode_of_payment"})
	key = _key(data.get("request_key"))
	existing = frappe.db.get_value("Payment Entry", {KEY: key}, "name")
	if existing:
		pe = frappe.get_doc("Payment Entry", existing)
		invoice_names = frappe.get_all("Purchase Invoice Item", filters={"purchase_order": doc.name}, pluck="parent", distinct=True)
		linked = any(
			(row.reference_doctype == "Purchase Order" and row.reference_name == doc.name)
			or (row.reference_doctype == "Purchase Invoice" and row.reference_name in invoice_names)
			for row in pe.references
		)
		if pe.company != doc.company or pe.party != doc.supplier or not linked:
			frappe.throw(_("This payment key belongs to another purchase."))
		return get_purchase(name)
	amount = _number(data.get("amount"), "payment amount")
	posting = _date(data.get("posting_date"), "Payment posting date")
	account = frappe.db.get_value("Account", data.get("paid_from"), ["name", "account_type", "company", "account_currency", "disabled", "is_group"], as_dict=True)
	if not account or account.company != doc.company or account.is_group or account.disabled or account.account_type not in ("Bank", "Cash") or account.account_currency != doc.currency:
		frappe.throw(_("Choose an enabled bank or cash ledger in the purchase currency."))
	invoice_name = cstr(data.get("invoice")).strip()
	if invoice_name:
		invoice = frappe.get_doc("Purchase Invoice", invoice_name)
		if invoice.docstatus != 1 or invoice.is_return or invoice.supplier != doc.supplier or invoice.company != doc.company or any(row.purchase_order != doc.name for row in invoice.items):
			frappe.throw(_("Choose a posted invoice belonging to this purchase."))
		maximum = flt(invoice.outstanding_amount, 2)
		dt, dn = "Purchase Invoice", invoice.name
	else:
		if not _setup()["ready"]:
			frappe.throw(_("An Accounts Manager must enable supplier advance accounting first."))
		if flt(doc.per_billed) > 0:
			frappe.throw(_("Once a bill is posted, pay its outstanding amount instead of adding an order advance."))
		maximum = flt(doc.grand_total - doc.advance_paid, 2)
		dt, dn = "Purchase Order", doc.name
	if amount > maximum or maximum <= 0:
		frappe.throw(_("Payment exceeds the remaining amount {0}.").format(maximum))
	if account.account_type == "Cash":
		cash_limit = flt(get_accounting_settings().get("cash_payment_limit") or 2000)
		if amount > cash_limit:
			frappe.throw(_("Cash payments cannot exceed {0}. Select a bank ledger.").format(cash_limit))
	if account.account_type == "Bank" and not cstr(data.get("reference_no")).strip():
		frappe.throw(_("Enter the bank transaction reference."))
	reference_date = _date(data.get("reference_date") or posting, "Transaction reference date")
	mode = cstr(data.get("mode_of_payment")).strip()
	if mode and not frappe.db.exists("Mode of Payment", {"name": mode, "enabled": 1, "type": account.account_type}):
		frappe.throw(_("Choose a payment mode matching the selected bank or cash ledger."))
	actor = _user()
	with _accounting_context():
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		pe = get_payment_entry(dt, dn, party_amount=amount, bank_account=account.name, bank_amount=amount)
		pe.posting_date = posting
		pe.reference_no = cstr(data.get("reference_no")).strip() if account.account_type == "Bank" else None
		pe.reference_date = reference_date if account.account_type == "Bank" else None
		pe.mode_of_payment = mode or ("Cash" if account.account_type == "Cash" and frappe.db.exists("Mode of Payment", "Cash") else None)
		pe.set(KEY, key)
		pe.owner = actor
		pe.insert()
		pe.submit()
		_audit(pe, "supplier advance" if not invoice_name else "supplier invoice payment", actor)
	return get_purchase(name)


@frappe.whitelist(methods=["POST"])
def create_purchase_master(kind, details):
	_require_accounts(manager=True)
	if kind == "supplier":
		data = _data(details, {"name", "phone", "address", "pan", "gstin"})
		if any(not cstr(data.get(key)).strip() for key in ("name", "phone", "address", "pan")):
			frappe.throw(_("Enter supplier name, phone, address and PAN."))
		if frappe.db.exists("Supplier", {"supplier_name": cstr(data["name"]).strip()}):
			frappe.throw(_("A supplier with this name already exists. Select it from the list."))
		doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": cstr(data["name"]).strip()[:140], "supplier_type": "Company", "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"), "tax_id": cstr(data.get("gstin")).strip(), "supplier_details": "<br>".join(f"{label}: {escape(cstr(data[key]).strip())}" for key, label in (("pan", "PAN"), ("phone", "Phone"), ("address", "Address")))})
		if doc.meta.has_field("pan"):
			doc.pan = cstr(data["pan"]).strip().upper()
	elif kind == "item":
		data = _data(details, {"name", "uom"})
		if not cstr(data.get("name")).strip() or not frappe.db.exists("UOM", data.get("uom")):
			frappe.throw(_("Enter an item name and existing unit of measure."))
		doc = frappe.get_doc({"doctype": "Item", "item_code": cstr(data["name"]).strip()[:140], "item_name": cstr(data["name"]).strip()[:140], "stock_uom": data["uom"], "item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"), "is_stock_item": 0, "is_purchase_item": 1, "is_sales_item": 0})
	else:
		frappe.throw(_("Choose supplier or item."))
	doc.insert(ignore_permissions=True)
	return {"name": doc.name}
