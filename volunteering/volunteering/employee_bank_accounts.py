"""Employee-submitted reimbursement bank accounts with Accounts Manager approval."""

from __future__ import annotations

import base64
import binascii
import re
from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.utils import cint, cstr, now_datetime

from volunteering.volunteering.authority import get_employee_for_user

REQUEST_DOCTYPE = "Employee Bank Account Request"
ACCOUNTS_MANAGER_ROLE = "Accounts Manager"
PENDING = "Pending Approval"
APPROVED = "Approved"
IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
SWIFT_PATTERN = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")
ACCOUNT_PATTERN = re.compile(r"^[A-Z0-9]{6,30}$")
ACCOUNT_TYPES = {"Savings", "Current", "Salary", "Other"}

_request_mutation = ContextVar("employee_bank_request_mutation", default=False)
_approved_bank_write = ContextVar("approved_employee_bank_write", default=False)


@contextmanager
def request_mutation():
	token = _request_mutation.set(True)
	try:
		yield
	finally:
		_request_mutation.reset(token)


def request_mutation_allowed():
	return _request_mutation.get()


@contextmanager
def approved_bank_write():
	token = _approved_bank_write.set(True)
	try:
		yield
	finally:
		_approved_bank_write.reset(token)


def validate_employee_bank_account_change(doc, method=None):
	"""Block direct edits to Employee party accounts outside approved requests."""
	previous = doc.get_doc_before_save()
	if (
		doc.get("party_type") == "Employee" or (previous and previous.party_type == "Employee")
	) and not _approved_bank_write.get():
		frappe.throw(
			_(
				"Employee reimbursement accounts can only be changed through an approved bank-account request."
			),
			frappe.PermissionError,
		)


def _logged_in():
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Log in to manage reimbursement bank details."), frappe.PermissionError)


def _is_accounts_manager(user=None):
	return ACCOUNTS_MANAGER_ROLE in frappe.get_roles(user or frappe.session.user)


def _require_accounts_manager():
	_logged_in()
	if not _is_accounts_manager():
		frappe.throw(
			_("Only a user with the Accounts Manager role may approve, return or reject bank details."),
			frappe.PermissionError,
		)


def _employee_for_current_user(required=True):
	_logged_in()
	employee = get_employee_for_user(frappe.session.user)
	if employee and frappe.db.get_value("Employee", employee, "status") != "Active":
		employee = None
	if required and not employee:
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def _clean(value, label, length, required=False):
	value = " ".join(cstr(value).strip().split())
	if required and not value:
		frappe.throw(_("{0} is required.").format(label))
	if len(value) > length:
		frappe.throw(_("{0} cannot exceed {1} characters.").format(label, length))
	return value


def _normalise_details(details):
	details = frappe.parse_json(details)
	if not isinstance(details, dict):
		frappe.throw(_("Bank details must be a valid object."))
	if details.get("ownership_confirmed") not in (True, 1, "1"):
		frappe.throw(
			_("Confirm that this account belongs to you and the proof contains the correct details.")
		)
	account_number = re.sub(r"[\s-]+", "", cstr(details.get("account_number"))).upper()
	confirmation = re.sub(r"[\s-]+", "", cstr(details.get("account_number_confirmation"))).upper()
	if account_number != confirmation:
		frappe.throw(_("The account number confirmation does not match."))
	if not ACCOUNT_PATTERN.fullmatch(account_number):
		frappe.throw(_("Enter a valid bank account number containing 6 to 30 letters or digits."))
	ifsc = _clean(details.get("ifsc"), _("IFSC"), 11, required=True).upper()
	if not IFSC_PATTERN.fullmatch(ifsc):
		frappe.throw(_("IFSC must contain four letters, zero, and six letters or digits."))
	swift = _clean(details.get("swift"), _("SWIFT"), 11).upper()
	if swift and not SWIFT_PATTERN.fullmatch(swift):
		frappe.throw(_("SWIFT must contain 8 or 11 letters or digits."))
	account_type = _clean(details.get("account_type"), _("Account type"), 20, required=True)
	if account_type not in ACCOUNT_TYPES:
		frappe.throw(_("Choose a valid account type."))
	return {
		"account_holder_name": _clean(
			details.get("account_holder_name"), _("Account holder name"), 160, required=True
		),
		"bank_name": _clean(details.get("bank_name"), _("Bank name"), 100, required=True),
		"branch": _clean(details.get("branch"), _("Branch"), 140),
		"account_type": account_type,
		"account_number": account_number,
		"account_number_last4": account_number[-4:],
		"ifsc": ifsc,
		"swift": swift,
	}


def _proof(details):
	filename = cstr(details.get("proof_filename"))
	encoded = cstr(details.get("proof_content"))
	if not filename or len(encoded) > 7_000_000:
		frappe.throw(_("Attach a cancelled cheque or bank proof in PDF, PNG or JPEG format (maximum 5 MB)."))
	try:
		content = base64.b64decode(encoded, validate=True)
	except ValueError, binascii.Error:
		frappe.throw(_("The bank proof is invalid."))
	if not content or len(content) > 5 * 1024 * 1024:
		frappe.throw(_("Bank proof must be smaller than 5 MB."))
	extension = filename.rsplit(".", 1)[-1].lower()
	valid = (
		(extension == "pdf" and content.startswith(b"%PDF-"))
		or (extension == "png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
		or (extension in ("jpg", "jpeg") and content.startswith(b"\xff\xd8\xff"))
	)
	if not valid:
		frappe.throw(_("Bank proof must be a PDF, PNG or JPEG file matching its extension."))
	return content, extension


def has_permission(doc, user=None, ptype=None, **kwargs):
	return ptype in ("read", "select", "report") and _is_accounts_manager(user)


def get_permission_query_conditions(user=None):
	return "" if _is_accounts_manager(user) else "1=0"


def scoped_file(doc):
	return doc.attached_to_doctype == REQUEST_DOCTYPE and doc.attached_to_name


def can_read_file(doc, user=None):
	if not scoped_file(doc):
		return True
	user = user or frappe.session.user
	return user != "Guest" and (
		_is_accounts_manager(user)
		or frappe.db.get_value(REQUEST_DOCTYPE, doc.attached_to_name, "submitted_by") == user
	)


def validate_bank_proof_change(doc, method=None):
	previous = doc.get_doc_before_save()
	if scoped_file(doc) or (previous and scoped_file(previous)):
		if not _request_mutation.get():
			frappe.throw(
				_("Submitted bank proof cannot be changed; submit a new request instead."),
				frappe.PermissionError,
			)
		if not cint(doc.is_private):
			frappe.throw(_("Bank proof must be stored privately."))


def validate_bank_share(doc, method=None):
	if doc.share_doctype == REQUEST_DOCTYPE or (
		doc.share_doctype == "File" and scoped_file(frappe.get_doc("File", doc.share_name))
	):
		frappe.throw(_("Bank-account requests and proof cannot be shared."), frappe.PermissionError)


def _account_number(doc):
	return doc.get_password("account_number", raise_exception=False) or ""


def _mask(last4):
	return f"••••••{last4}" if last4 else ""


def _serialize(doc, reveal=False):
	row = {
		"name": doc.name,
		"modified": str(doc.modified),
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"submitted_by": doc.submitted_by,
		"request_status": doc.request_status,
		"account_holder_name": doc.account_holder_name,
		"bank_name": doc.bank_name,
		"branch": doc.branch or "",
		"account_type": doc.account_type,
		"account_number_masked": _mask(doc.account_number_last4),
		"ifsc": doc.ifsc,
		"swift": doc.swift or "",
		"review_comments": doc.review_comments or "",
		"reviewed_by": doc.reviewed_by,
		"reviewed_on": doc.reviewed_on,
		"bank_account": doc.bank_account,
		"creation": str(doc.creation),
		"proof_url": doc.proof_file,
	}
	if reveal:
		row["account_number"] = _account_number(doc)
	return row


def _requests(filters, reveal=False, limit=100):
	rows = frappe.get_all(
		REQUEST_DOCTYPE,
		filters=filters,
		pluck="name",
		order_by="creation desc",
		limit=limit,
	)
	return [_serialize(frappe.get_doc(REQUEST_DOCTYPE, name), reveal=reveal) for name in rows]


@frappe.whitelist()
def get_bank_account_workspace():
	"""Return own masked history and, for Accounts Managers, the review queue."""
	employee = _employee_for_current_user(required=False)
	manager = _is_accounts_manager()
	if not employee and not manager:
		frappe.throw(_("Employee or Accounts Manager access is required."), frappe.PermissionError)
	approved = None
	own_requests = []
	if employee:
		own_requests = _requests({"employee": employee}, reveal=False)
		approved = next((row for row in own_requests if row["request_status"] == APPROVED), None)
	return {
		"employee": employee,
		"can_submit": bool(employee),
		"can_review": manager,
		"approved": approved,
		"requests": own_requests,
		"pending_requests": _requests({"request_status": PENDING}, reveal=True) if manager else [],
	}


@frappe.whitelist(methods=["POST"])
def submit_bank_account_request(details):
	employee = _employee_for_current_user()
	# All requests/decisions for one employee serialize on the same parent row.
	frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name=%s FOR UPDATE", employee)
	if frappe.db.exists(REQUEST_DOCTYPE, {"employee": employee, "request_status": PENDING}):
		frappe.throw(_("A bank-account request is already awaiting review."))
	details = frappe.parse_json(details)
	values = _normalise_details(details)
	proof, extension = _proof(details)
	doc = frappe.new_doc(REQUEST_DOCTYPE)
	doc.update(
		{
			"employee": employee,
			"submitted_by": frappe.session.user,
			"request_status": PENDING,
			"ownership_confirmed": 1,
			**values,
		}
	)
	with request_mutation():
		doc.insert(ignore_permissions=True)
		from frappe.utils.file_manager import save_file

		file = save_file(f"bank-proof-{doc.name}.{extension}", proof, REQUEST_DOCTYPE, doc.name, is_private=1)
		doc.proof_file = file.file_url
		doc.save(ignore_permissions=True)
	return _serialize(doc)


def _load_pending(request, modified=None):
	if not modified:
		frappe.throw(_("Reload the request before deciding."), frappe.TimestampMismatchError)
	frappe.db.sql(f"SELECT name FROM `tab{REQUEST_DOCTYPE}` WHERE name=%s FOR UPDATE", request)
	doc = frappe.get_doc(REQUEST_DOCTYPE, request)
	if modified is not None and str(doc.modified) != modified:
		frappe.throw(_("This request changed. Reload before deciding."), frappe.TimestampMismatchError)
	if doc.request_status != PENDING:
		frappe.throw(_("This request is no longer awaiting approval."))
	return doc


def _ensure_bank(bank_name):
	bank = frappe.db.exists("Bank", bank_name)
	if not bank:
		doc = frappe.get_doc({"doctype": "Bank", "bank_name": bank_name})
		doc.insert(ignore_permissions=True)
		return doc.name
	return bank


def _publish_approved_account(doc):
	account_number = _account_number(doc)
	if not account_number:
		frappe.throw(_("The submitted account number is unavailable. Return this request for correction."))
	bank = _ensure_bank(doc.bank_name)
	# A new account per approval preserves historical payment destinations—even
	# when an employee's replacement happens to have the same last four digits.
	bank_account = frappe.new_doc("Bank Account")
	bank_account.update(
		{
			"account_name": f"{doc.employee} {doc.name}",
			"bank": bank,
			"account_type": doc.account_type
			if frappe.db.exists("Bank Account Type", doc.account_type)
			else None,
			"is_company_account": 0,
			"party_type": "Employee",
			"party": doc.employee,
			"bank_account_no": account_number,
			"branch_code": doc.ifsc,
			"mask": doc.account_number_last4,
			"is_default": 1,
			"disabled": 0,
		}
	)
	with approved_bank_write():
		bank_account.insert(ignore_permissions=True)

	old_requests = frappe.get_all(
		REQUEST_DOCTYPE,
		filters={"employee": doc.employee, "request_status": APPROVED, "name": ["!=", doc.name]},
		pluck="name",
	)
	for old_name in old_requests:
		old = frappe.get_doc(REQUEST_DOCTYPE, old_name)
		old.request_status = "Superseded"
		with request_mutation():
			old.save(ignore_permissions=True)
		if (
			old.bank_account
			and old.bank_account != bank_account.name
			and frappe.db.exists("Bank Account", old.bank_account)
		):
			old_account = frappe.get_doc("Bank Account", old.bank_account)
			old_account.disabled = 1
			old_account.is_default = 0
			with approved_bank_write():
				old_account.save(ignore_permissions=True)

	return bank_account.name


@frappe.whitelist(methods=["POST"])
def review_bank_account_request(request, action, modified, comments=""):
	_require_accounts_manager()
	action = cstr(action).strip().lower()
	if action not in {"approve", "return", "reject"}:
		frappe.throw(_("Choose Approve, Return or Reject."))
	comments = _clean(comments, _("Review comments"), 500)
	if action != "approve" and not comments:
		frappe.throw(_("Comments are required when returning or rejecting bank details."))
	doc = _load_pending(request, modified)
	frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name=%s FOR UPDATE", doc.employee)
	if frappe.db.get_value("Employee", doc.employee, "status") != "Active":
		frappe.throw(_("Only an active employee's bank details can be reviewed."))
	if _account_number(doc) in comments:
		frappe.throw(_("Do not include the full account number in review comments."))
	if action == "approve":
		if not doc.proof_file or not frappe.db.exists(
			"File",
			{
				"file_url": doc.proof_file,
				"attached_to_doctype": REQUEST_DOCTYPE,
				"attached_to_name": doc.name,
				"is_private": 1,
			},
		):
			frappe.throw(_("Private bank proof is required before approval."))
		doc.bank_account = _publish_approved_account(doc)
		doc.request_status = APPROVED
	elif action == "return":
		doc.request_status = "Returned"
	else:
		doc.request_status = "Rejected"
	doc.review_comments = comments
	doc.reviewed_by = frappe.session.user
	doc.reviewed_on = now_datetime()
	with request_mutation():
		doc.save(ignore_permissions=True)
	return _serialize(doc, reveal=True)


def get_approved_bank_details(employee, reveal=True):
	"""Canonical remittance details; unapproved ERPNext Bank Accounts are ignored."""
	name = frappe.db.get_value(
		REQUEST_DOCTYPE,
		{"employee": employee, "request_status": APPROVED},
		"name",
		order_by="reviewed_on desc",
	)
	if not name:
		return None
	doc = frappe.get_doc(REQUEST_DOCTYPE, name)
	if not _matches_approved_account(doc):
		frappe.throw(_("The approved bank record is unavailable or changed. Contact your Accounts Manager."))
	row = _serialize(doc, reveal=reveal)
	return {
		"request": row["name"],
		"bank_name": row["bank_name"],
		"branch": row["branch"],
		"account_name": row["account_holder_name"],
		"account_number": row.get("account_number") if reveal else row["account_number_masked"],
		"account_number_masked": row["account_number_masked"],
		"ifsc": row["ifsc"],
		"swift": row["swift"],
	}


def _matches_approved_account(doc):
	if not doc.bank_account or not frappe.db.exists("Bank Account", doc.bank_account):
		return False
	bank = frappe.get_doc("Bank Account", doc.bank_account)
	return (
		not bank.disabled
		and not bank.is_company_account
		and bank.party_type == "Employee"
		and bank.party == doc.employee
		and bank.bank == doc.bank_name
		and bank.branch_code == doc.ifsc
		and bank.bank_account_no == _account_number(doc)
	)


def validate_employee_payment_bank(doc, method=None):
	"""Only approved destinations may be used for employee bank remittances."""
	if doc.payment_type != "Pay" or doc.party_type != "Employee" or not doc.party:
		return
	if frappe.db.get_value("Account", doc.paid_from, "account_type") != "Bank":
		return  # Cash reimbursements do not require a personal bank account.
	# Keep approval/replacement and payment submission for one employee atomic.
	frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name=%s FOR UPDATE", doc.party)
	approved_name = frappe.db.get_value(
		REQUEST_DOCTYPE, {"employee": doc.party, "request_status": APPROVED}, "name"
	)
	if not approved_name:
		frappe.throw(
			_("An Accounts Manager must approve this employee's bank details before bank reimbursement.")
		)
	request = frappe.get_doc(REQUEST_DOCTYPE, approved_name)
	if not _matches_approved_account(request):
		frappe.throw(_("The employee's approved bank details are unavailable or changed."))
	if doc.party_bank_account and doc.party_bank_account != request.bank_account:
		frappe.throw(_("Select the employee's currently approved reimbursement bank account."))
	doc.party_bank_account = request.bank_account
