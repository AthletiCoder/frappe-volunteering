"""Employee withdrawal is terminal and never reverses a posted accounting entry."""
import frappe
from frappe import _
from frappe.utils import cstr, flt, now_datetime

WITHDRAWABLE_STATES = {"Draft", "Pending Receipt Review", "Receipt Correction Required", "Pending Approval", "Rejected"}


def can_withdraw(doc):
	return (int(doc.docstatus or 0) == 0 and doc.get("workflow_state") in WITHDRAWABLE_STATES
		and doc.get("approval_status") != "Approved" and not flt(doc.get("total_amount_reimbursed")))


def validate_closed_claim(doc, method=None):
	previous = doc.get_doc_before_save() if not doc.is_new() else None
	if doc.get("workflow_state") == "Withdrawn" or previous and previous.get("workflow_state") == "Withdrawn":
		frappe.throw(_("A withdrawn claim is closed and cannot be edited, resubmitted or posted. Submit a new claim if needed."))


def _own_locked(name):
	from volunteering.volunteering.expense_claim_portal import _require_employee
	from volunteering.volunteering.home_cutover import require_home_project

	employee = _require_employee()
	doc = frappe.get_doc("Expense Claim", cstr(name).strip(), for_update=True)
	if doc.employee != employee:
		frappe.throw(_("You can only withdraw your own claims."), frappe.PermissionError)
	require_home_project(doc.project)
	return doc


@frappe.whitelist(methods=["POST"])
def withdraw_expense_claim(name, expected_modified, reason):
	from volunteering.volunteering.expense_claim_portal import get_my_expense_claim

	doc = _own_locked(name)
	# Safe retry if the withdrawal succeeded but its confirmation was lost.
	if doc.workflow_state == "Withdrawn":
		return get_my_expense_claim(doc.name)
	if not can_withdraw(doc):
		frappe.throw(_("This claim is already approved, posted or settled. Contact Accounts about cancellation."))
	if cstr(doc.modified) != cstr(expected_modified):
		frappe.throw(_("This claim changed. Refresh it before withdrawing."))
	reason = cstr(reason).strip()
	if not reason or len(reason) > 1000:
		frappe.throw(_("Give a withdrawal reason of up to 1000 characters."))
	if frappe.db.exists("GL Entry", {"voucher_type": "Expense Claim", "voucher_no": doc.name, "is_cancelled": 0}):
		frappe.throw(_("This claim has accounting entries. Accounts must handle its cancellation."))
	# Keep claimed amounts, receipt links and advances as evidence. Pending advance
	# allocations have not been posted; no paid/claimed advance balance is changed.
	doc.db_set({"workflow_state": "Withdrawn", "pending_approver": None, "expense_approver": None,
		"withdrawn_by": frappe.session.user, "withdrawn_on": now_datetime(), "withdrawal_reason": reason})
	doc.add_comment("Comment", _("Claim withdrawn by {0}: {1}").format(frappe.session.user, frappe.utils.escape_html(reason)))
	frappe.db.set_value("Workflow Action", {"reference_doctype": "Expense Claim", "reference_name": doc.name, "status": "Open"},
		{"status": "Completed", "completed_by": frappe.session.user})
	frappe.publish_realtime("doc_update", {"doctype": doc.doctype, "name": doc.name}, doctype=doc.doctype, docname=doc.name, after_commit=True)
	return get_my_expense_claim(doc.name)


@frappe.whitelist(methods=["POST"])
def delete_expense_claim_draft(name, expected_modified):
	doc = _own_locked(name)
	if doc.docstatus != 0 or doc.workflow_state != "Draft":
		frappe.throw(_("Only an unsubmitted draft can be deleted. Withdraw a pending claim instead."))
	if cstr(doc.modified) != cstr(expected_modified):
		frappe.throw(_("This draft changed. Refresh before deleting it."))
	frappe.delete_doc("Expense Claim", doc.name, ignore_permissions=True)
	return {"name": doc.name, "deleted": True}
