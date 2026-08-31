# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Reimburse employee expense claims from a reporting manager's advance float."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.approval_routing import get_document_amount, get_reports_to_user
from volunteering.volunteering.desk_routes import desk_route
from volunteering.volunteering.employee_advance_controls import (
	advance_residual_amount,
	is_blocking_advance,
	list_open_advances_for_employee,
)

REIMBURSEMENT_OUT_OF_POCKET = "Out of Pocket"
REIMBURSEMENT_MANAGER_ADVANCE = "Manager Advance"


def is_manager_float_claim(doc) -> bool:
	return (doc.get("reimbursement_source") or REIMBURSEMENT_OUT_OF_POCKET) == REIMBURSEMENT_MANAGER_ADVANCE


def get_direct_manager_employee(employee: str | None) -> str | None:
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "reports_to")


def sync_manager_float_holder(doc) -> None:
	"""Keep manager_float_holder aligned with reports_to when using manager advance."""
	if not is_manager_float_claim(doc) or not doc.get("employee"):
		doc.manager_float_holder = None
		return
	doc.manager_float_holder = get_direct_manager_employee(doc.employee)


def list_fundable_manager_advances(manager_employee: str, min_amount: float = 0) -> list[dict]:
	"""Paid advances with enough residual for at least min_amount."""
	if not manager_employee:
		return []

	out = []
	for row in list_open_advances_for_employee(manager_employee):
		if row.docstatus != 1 or flt(row.paid_amount) <= 0:
			continue
		residual = advance_residual_amount(row)
		if residual < flt(min_amount):
			continue
		out.append(
			{
				"name": row.name,
				"residual": residual,
				"paid_amount": flt(row.paid_amount),
				"claimed_amount": flt(row.claimed_amount),
				"status": row.status,
				"workflow_state": row.get("workflow_state"),
				"purpose": row.get("purpose"),
			}
		)
	out.sort(key=lambda r: flt(r["residual"]), reverse=True)
	return out


def pick_manager_advance(manager_employee: str, amount: float) -> str | None:
	advances = list_fundable_manager_advances(manager_employee, amount)
	if not advances:
		return None
	return advances[0]["name"]


def manager_float_funding_status(doc) -> dict:
	"""Whether the direct manager can fund this claim from an advance."""
	amount = get_document_amount(doc)
	manager = doc.get("manager_float_holder") or get_direct_manager_employee(doc.get("employee"))
	if not manager:
		return {
			"eligible": False,
			"manager_employee": None,
			"manager_user": None,
			"manager_name": None,
			"available_residual": 0,
			"advance_name": None,
			"message": _("No reporting manager is set on your employee record."),
		}

	manager_user = frappe.db.get_value("Employee", manager, "user_id")
	manager_name = frappe.db.get_value("Employee", manager, "employee_name")
	advances = list_fundable_manager_advances(manager, amount)
	advance_name = advances[0]["name"] if advances else None
	available = flt(advances[0]["residual"]) if advances else 0

	if advance_name:
		message = _("Manager {0} can fund this from advance {1} ({2} available).").format(
			manager_name or manager,
			advance_name,
			frappe.format_value(available, "Currency"),
		)
	else:
		message = _(
			"Manager {0} has no paid advance with at least {1} available. "
			"Escalate or ask them to request an advance."
		).format(
			manager_name or manager,
			frappe.format_value(amount, "Currency"),
		)

	return {
		"eligible": bool(advance_name),
		"manager_employee": manager,
		"manager_user": manager_user,
		"manager_name": manager_name,
		"available_residual": available,
		"advance_name": advance_name,
		"advances": advances,
		"message": message,
	}


def validate_manager_float_expense_claim(doc, method=None) -> None:
	if doc.doctype != "Expense Claim":
		return

	sync_manager_float_holder(doc)

	if not is_manager_float_claim(doc):
		return

	if not doc.get("employee"):
		frappe.throw(_("Employee is required for a manager advance reimbursement request."))

	_validate_employee_has_no_blocking_advance_for_manager_float(doc)

	manager = doc.get("manager_float_holder")
	if not manager:
		frappe.throw(
			_(
				"Manager Advance reimbursement requires a reporting manager on your Employee record. "
				"Use Out of Pocket or ask HR to fix Reports To."
			)
		)

	if doc.docstatus == 0 and doc.get("workflow_state") in (None, "", "Draft"):
		# Draft: inform only; funding may appear before submit.
		return


def _employee_own_blocking_advance(employee: str | None):
	"""Open own advance that should force Get Advances / Out of Pocket (not manager float)."""
	if not employee:
		return None
	from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
		get_accounting_settings,
	)

	settings = get_accounting_settings()
	replenish_pct = flt(settings.get("advance_replenish_residual_pct"))
	if settings.get("advance_replenish_residual_pct") is None:
		replenish_pct = 10.0

	for row in list_open_advances_for_employee(employee):
		# Cancelled already excluded; drafts and unpaid residuals still block manager float.
		if is_blocking_advance(row, replenish_pct):
			return row
	return None


def _validate_employee_has_no_blocking_advance_for_manager_float(doc) -> None:
	"""Staff with their own unsettled advance must settle via Get Advances, not manager float."""
	blocking = _employee_own_blocking_advance(doc.employee)
	if not blocking:
		return

	frappe.throw(
		_(
			"You have an unsettled Employee Advance ({0}). "
			"Link this expense to your advance with Get Advances, or choose Out of Pocket. "
			"Manager Advance is for staff who do not have their own open float."
		).format(blocking.name),
		title=_("Use Your Own Advance"),
	)


def validate_manager_float_on_approve(doc) -> None:
	"""Block Approve when manager float is selected but manager cannot fund."""
	if doc.doctype != "Expense Claim" or not is_manager_float_claim(doc):
		return

	previous = doc.get_doc_before_save()
	if not previous or previous.workflow_state == "Approved" or doc.workflow_state != "Approved":
		return

	status = manager_float_funding_status(doc)
	if not status["eligible"]:
		frappe.throw(status["message"], title=_("Manager Advance Unavailable"))


def enrich_approver_action_flags(doc, flags: dict) -> dict:
	"""Adjust Approve/Escalate when claim uses manager float and approver is the manager."""
	if doc.doctype != "Expense Claim" or not is_manager_float_claim(doc):
		return flags

	if not flags.get("is_pending_approver"):
		return flags

	manager_user = frappe.db.get_value("Employee", doc.get("manager_float_holder"), "user_id")
	if frappe.session.user != manager_user:
		return flags

	status = manager_float_funding_status(doc)
	if not status["eligible"]:
		flags["can_approve"] = False
		flags["can_escalate"] = True
		flags["manager_float_blocked"] = True
		flags["manager_float_message"] = status["message"]
	else:
		flags["manager_float_advance"] = status["advance_name"]
		flags["manager_float_message"] = status["message"]
	return flags


def settle_expense_claim_from_manager_float(doc) -> None:
	"""After Approve: allocate claim amount to manager advance; mark claim reimbursed in books."""
	if doc.doctype != "Expense Claim" or not is_manager_float_claim(doc):
		return

	previous = doc.get_doc_before_save()
	if not previous or previous.workflow_state == "Approved" or doc.workflow_state != "Approved":
		return

	amount = flt(doc.total_sanctioned_amount or doc.total_claimed_amount or doc.grand_total)
	if amount <= 0:
		return

	manager = doc.get("manager_float_holder")
	advance_name = doc.get("manager_float_advance") or pick_manager_advance(manager, amount)
	if not advance_name:
		frappe.throw(_("Cannot settle: no manager advance with sufficient residual."), title=_("Settlement Failed"))

	advance = frappe.get_doc("Employee Advance", advance_name)
	residual = advance_residual_amount(advance)
	if amount > residual + 0.01:
		frappe.throw(
			_("Cannot settle {0}: advance {1} only has {2} residual.").format(
				frappe.format_value(amount, "Currency"),
				advance_name,
				frappe.format_value(residual, "Currency"),
			),
			title=_("Insufficient Manager Float"),
		)

	new_claimed = flt(advance.claimed_amount) + amount
	frappe.db.set_value(
		"Employee Advance",
		advance_name,
		"claimed_amount",
		new_claimed,
		update_modified=False,
	)
	_update_advance_status(advance_name)

	frappe.db.set_value(
		"Expense Claim",
		doc.name,
		{
			"manager_float_advance": advance_name,
			"total_amount_reimbursed": amount,
		},
		update_modified=False,
	)

	doc.manager_float_advance = advance_name
	doc.total_amount_reimbursed = amount


def settle_manager_float_expense_claim_on_submit(doc, method=None) -> None:
	"""Approve calls submit() after HRMS workflow; settle once GL/reimbursed fields are final."""
	if doc.doctype != "Expense Claim" or not is_manager_float_claim(doc):
		return
	if doc.workflow_state != "Approved":
		return

	settle_expense_claim_from_manager_float(doc)
	amount = flt(doc.total_sanctioned_amount or doc.total_claimed_amount or doc.grand_total)
	if amount > 0 and doc.get("manager_float_advance"):
		frappe.db.set_value(
			"Expense Claim",
			doc.name,
			"total_amount_reimbursed",
			amount,
			update_modified=False,
		)
		doc.total_amount_reimbursed = amount


def _update_advance_status(advance_name: str) -> None:
	advance = frappe.get_doc("Employee Advance", advance_name)
	paid = flt(advance.paid_amount)
	claimed = flt(advance.claimed_amount)
	returned = flt(advance.return_amount)
	residual = max(paid - claimed - returned, 0)

	if residual <= 0.01 and paid > 0:
		status = "Claimed"
	elif claimed > 0:
		status = "Partly Claimed and Returned" if returned > 0 else "Unpaid"
	else:
		status = advance.status or "Paid"

	if status != advance.status:
		frappe.db.set_value("Employee Advance", advance_name, "status", status, update_modified=False)


@frappe.whitelist()
def get_manager_float_context(employee=None):
	"""Portal: employee view — manager, fundable advances, draft guidance."""
	employee = _resolve_session_employee(employee)
	manager = get_direct_manager_employee(employee)
	manager_name = frappe.db.get_value("Employee", manager, "employee_name") if manager else None
	advances = list_fundable_manager_advances(manager) if manager else []
	total_residual = sum(flt(a["residual"]) for a in advances)
	own_blocking = _employee_own_blocking_advance(employee)
	can_request = bool(manager) and not own_blocking

	return {
		"employee": employee,
		"manager_employee": manager,
		"manager_name": manager_name,
		"manager_user": get_reports_to_user(employee) if employee else None,
		"fundable_advances": advances,
		"total_residual": total_residual,
		"can_request": can_request,
		"own_blocking_advance": own_blocking.name if own_blocking else None,
		"block_reason": (
			_("You have an unsettled Employee Advance ({0}). Use Get Advances or Out of Pocket.")
			.format(own_blocking.name)
			if own_blocking
			else None
		),
		"new_claim_url": desk_route("Expense Claim", "new"),
	}


@frappe.whitelist()
def get_team_manager_float_requests():
	"""Portal: manager view — pending claims requesting manager advance from reportees."""
	manager = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not manager:
		frappe.throw(_("Your user is not linked to an Employee record."))

	reportees = frappe.get_all(
		"Employee",
		filters={"reports_to": manager, "status": "Active"},
		pluck="name",
	)
	if not reportees:
		return {"requests": [], "fundable_advances": list_fundable_manager_advances(manager)}

	claims = frappe.get_all(
		"Expense Claim",
		filters={
			"employee": ["in", reportees],
			"reimbursement_source": REIMBURSEMENT_MANAGER_ADVANCE,
			"workflow_state": "Pending Approval",
			"docstatus": 0,
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"project",
			"total_claimed_amount",
			"total_sanctioned_amount",
			"posting_date",
			"pending_approver",
		],
		order_by="modified desc",
		limit=50,
	)

	requests = []
	for row in claims:
		amount = flt(row.total_sanctioned_amount or row.total_claimed_amount)
		status = manager_float_funding_status(frappe._dict(**row, reimbursement_source=REIMBURSEMENT_MANAGER_ADVANCE))
		requests.append(
			{
				**row,
				"amount": amount,
				"route": desk_route("Expense Claim", row.name),
				"can_fund": status["eligible"],
				"funding_message": status["message"],
				"suggested_advance": status.get("advance_name"),
			}
		)

	return {
		"manager_employee": manager,
		"fundable_advances": list_fundable_manager_advances(manager),
		"requests": requests,
	}


def _resolve_session_employee(employee=None):
	roles = set(frappe.get_roles())
	staff = roles.intersection({"Accounts Manager", "Accounts User", "System Manager", "HR Manager", "HR User"})
	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if employee and staff:
		return employee
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))
	if employee and employee != session_employee and not staff:
		frappe.throw(_("You can only view your own manager float options."))
	return session_employee or employee
