# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee Advance NGO rules on top of HRMS."""

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate

# Fully settled advances have no outstanding balance.
SETTLED_STATUSES = ("Claimed", "Returned", "Cancelled")


def before_employee_advance_save(doc, method=None):
	from volunteering.volunteering.employee_advance_permissions import validate_employee_self_only

	validate_employee_self_only(doc, method)
	# Advances are staff float, not program spend. Do not tag to a Project.
	# Budget is checked on the Expense Claim (or PO) that settles the spend.
	if doc.get("project"):
		doc.project = None

	_ensure_currency(doc)
	_ensure_advance_account(doc)
	_validate_portal_request_fields(doc)
	# Multiple requests are allowed regardless of prior unpaid/unsettled balances.
	# Outstanding amounts determine live approval authority, never replenishment gates.


def _is_new_request_or_submission(doc):
	if doc.is_new():
		return True
	previous = doc.get_doc_before_save()
	if not previous:
		return False
	return (previous.get("workflow_state") or "Draft") in ("Draft", "Rejected") and (
		doc.get("workflow_state") or "Draft"
	) not in ("Draft", "Rejected")


def _validate_portal_request_fields(doc):
	"""Enforce the same eligibility rules from both Home and Desk."""
	if doc.flags.get("ignore_advance_eligibility"):
		return
	if not _is_new_request_or_submission(doc):
		return
	from volunteering.volunteering.advance_freeze import validate_not_frozen
	from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details

	validate_not_frozen(doc.employee)
	project_name = cstr(doc.get("intended_project")).strip()
	if not project_name:
		frappe.throw(_("Select an active Project in which you are a member."))
	_validate_advance_project(project_name, doc.employee)

	required_by = getdate(doc.get("required_by_date") or nowdate())
	settlement = getdate(doc.get("expected_settlement_date") or required_by)
	if required_by < getdate(nowdate()):
		frappe.throw(_("Required By cannot be in the past."))
	if settlement < required_by:
		frappe.throw(_("Expected Settlement Date cannot be before Required By."))
	doc.required_by_date = required_by
	doc.expected_settlement_date = settlement

	advance_use = cstr(doc.get("advance_use") or "My expenses").strip()
	if advance_use not in ("My expenses", "Team expenses"):
		frappe.throw(_("Choose a valid advance use."))
	if advance_use == "Team expenses" and not frappe.db.exists(
		"Employee", {"reports_to": doc.employee, "status": "Active"}
	):
		frappe.throw(_("Team expenses can only be selected by an employee with an active direct report."))
	doc.advance_use = advance_use

	if not get_approved_bank_details(doc.employee, reveal=False):
		frappe.throw(
			_(
				"An Accounts Manager must approve your reimbursement bank account before you request an advance."
			)
		)


def _validate_advance_project(project_name, employee):
	project = frappe.get_doc("Project", project_name)
	user = frappe.db.get_value("Employee", employee, "user_id")
	member = project.get("project_owner") == user or any(
		row.user == user for row in project.get("project_participants") or []
	)
	if not member:
		frappe.throw(_("You must be a listed member of the selected Project."), frappe.PermissionError)
	if not frappe.utils.cint(project.get("project_setup_version")):
		frappe.throw(_("The selected Project has not completed its approved setup."))
	if project.get("operational_status") != "Active":
		frappe.throw(_("Advance requests require an Active Project."))
	if project.get("budget_status") == "Closed" or frappe.utils.cint(project.get("is_archived")):
		frappe.throw(_("The selected Project is closed."))
	company = frappe.db.get_value("Employee", employee, "company")
	if project.company != company:
		frappe.throw(_("The selected Project belongs to a different Company."))
	return project


def _ensure_currency(doc):
	if doc.get("currency"):
		return
	company = doc.get("company")
	if not company and doc.get("employee"):
		company = frappe.db.get_value("Employee", doc.employee, "company")
	if company:
		doc.currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
	else:
		doc.currency = "INR"


def _ensure_advance_account(doc):
	if doc.get("advance_account") or not doc.get("employee"):
		return
	account = frappe.db.get_value("Employee", doc.employee, "employee_advance_account")
	if not account and doc.get("company"):
		account = frappe.db.get_value("Company", doc.company, "default_employee_advance_account")
	if account:
		doc.advance_account = account


def advance_residual_amount(row) -> float:
	"""Unsettled balance on an Employee Advance row/dict."""
	advance_amount = flt(row.get("advance_amount"))
	paid_amount = flt(row.get("paid_amount"))
	claimed_amount = flt(row.get("claimed_amount"))
	return_amount = flt(row.get("return_amount"))
	status = row.get("status") or ""

	if status in SETTLED_STATUSES or status == "Cancelled":
		return 0.0

	# Not yet disbursed: treat full request as residual
	if paid_amount <= 0:
		return advance_amount

	return max(paid_amount - claimed_amount - return_amount, 0.0)


def advance_residual_ratio(row) -> float:
	"""Residual as fraction of paid (or advance) amount. 0 = settled."""
	residual = advance_residual_amount(row)
	if residual <= 0:
		return 0.0

	paid_amount = flt(row.get("paid_amount"))
	advance_amount = flt(row.get("advance_amount"))
	base = paid_amount if paid_amount > 0 else advance_amount
	if base <= 0:
		return 0.0
	return residual / base


def is_blocking_advance(row, replenish_pct: float) -> bool:
	"""Manager-float source selection only; never a limit on new advance requests."""
	if (row.get("status") or "") in SETTLED_STATUSES:
		return False
	threshold = flt(replenish_pct) / 100.0
	if threshold < 0:
		threshold = 0.0
	return advance_residual_ratio(row) > threshold


def list_open_advances_for_employee(employee, exclude_name=None):
	filters = {
		"employee": employee,
		"docstatus": ["!=", 2],
	}
	rows = frappe.get_all(
		"Employee Advance",
		filters=filters,
		fields=[
			"name",
			"status",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"docstatus",
			"intended_project",
			"advance_use",
			"workflow_state",
			"purpose",
		],
	)
	if exclude_name:
		rows = [r for r in rows if r.name != exclude_name]
	return rows


def advance_counts_towards_approval_exposure(row) -> bool:
	"""Whether an advance contributes to the employee's live approval exposure.

	Drafts and rejected requests have not been accepted into the approval chain.
	Pending requests and approved/disbursed advances continue to count until their
	remaining commitment is claimed, returned, or cancelled.
	"""
	if int(row.get("docstatus") or 0) == 2 or (row.get("status") or "") == "Cancelled":
		return False
	workflow_state = (row.get("workflow_state") or "").strip()
	if workflow_state in ("Draft", "Rejected", "Cancelled"):
		return False
	if int(row.get("docstatus") or 0) == 0 and not (
		workflow_state == "Approved" or workflow_state.startswith("Pending")
	):
		return False
	return advance_approval_outstanding_amount(row) > 0


def advance_approval_outstanding_amount(row) -> float:
	"""Reserve active request value, including an approved unpaid remainder.

	The disbursed residual used for bill reconciliation is not sufficient for
	approval authority: a partly paid advance can still be paid the remainder.
	Keep that commitment in exposure until claims/returns reduce it or the
	advance is fully settled or cancelled. HRMS can label a partly disbursed
	advance Claimed/Returned even though its unpaid remainder is still payable,
	so those labels alone must not release that commitment.
	"""
	if int(row.get("docstatus") or 0) == 2 or (row.get("status") or "") == "Cancelled":
		return 0.0
	committed = max(flt(row.get("advance_amount")), flt(row.get("paid_amount")))
	return max(committed - flt(row.get("claimed_amount")) - flt(row.get("return_amount")), 0.0)


def get_advance_approval_exposure(employee, current_name=None, current_amount=0):
	"""Return the live amount against which an advance approver is authorised.

	The request currently being reviewed is always counted at its requested
	amount. Other active advances are read afresh from the database so a reviewer
	sees, and the approval action rechecks, the employee's current total exposure.
	"""
	request_amount = max(flt(current_amount), 0.0)
	other_outstanding = sum(
		advance_approval_outstanding_amount(row)
		for row in list_open_advances_for_employee(employee, exclude_name=current_name)
		if advance_counts_towards_approval_exposure(row)
	)
	return {
		"request_amount": flt(request_amount, 2),
		"other_outstanding": flt(other_outstanding, 2),
		"total_outstanding": flt(request_amount + other_outstanding, 2),
	}


def residual_advances_for_employee(employee):
	"""Open advances with any residual > 0 (for PE warnings / lists)."""
	rows = list_open_advances_for_employee(employee)
	return [
		{
			"name": r.name,
			"residual": advance_residual_amount(r),
			"ratio": advance_residual_ratio(r),
			"status": r.status,
		}
		for r in rows
		if advance_residual_amount(r) > 0
	]


@frappe.whitelist()
def get_grade_advance_limit_for_employee(employee):
	"""Compatibility endpoint for Desk clients: request amounts have no grade cap."""
	return {
		"limit": None,
		"label": _(
			"You may request any amount. Your reporting manager reviews first, then escalates one step at a time when your live total outstanding exceeds their approval authority."
		),
	}


@frappe.whitelist()
def get_linkable_advances_hint(employee):
	"""Explain why Get Advances may be empty (must be submitted + paid)."""
	if not employee:
		return ""

	rows = frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": ["!=", 2]},
		fields=["name", "docstatus", "paid_amount", "status", "workflow_state"],
	)
	if not rows:
		return _(
			"No Employee Advances found for this employee. Create and get an advance paid before linking."
		)

	linkable = [
		r
		for r in rows
		if r.docstatus == 1
		and flt(r.paid_amount) > 0
		and (r.status or "") not in ("Claimed", "Returned", "Partly Claimed and Returned")
	]
	if linkable:
		names = ", ".join(r.name for r in linkable[:5])
		return _("Advances available to link via Get Advances: {0}").format(names)

	parts = []
	for r in rows[:5]:
		if r.docstatus != 1:
			parts.append(_("{0}: not submitted yet").format(r.name))
		elif flt(r.paid_amount) <= 0:
			parts.append(_("{0}: approved but not paid by Accounts yet").format(r.name))
		else:
			parts.append(_("{0}: already {1}").format(r.name, r.status or _("settled")))

	return _(
		"No advances qualify for Get Advances yet (needs Submitted + Paid amount > 0 + not fully claimed). "
		"{0}"
	).format("; ".join(parts))
