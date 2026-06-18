import frappe
from frappe import _

from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)

ROLE_BOARD_CHAIR = "NGO Board Chairperson"
ROLE_BOARD_MEMBER = "NGO Board Member"
ROLE_DEPT_HEAD = "NGO Department Head"
ROLE_ACCOUNTS_MANAGER = "Accounts Manager"

PENDING_ROUTER_STATE = "Pending"

PENDING_EXPENSE_TIER_1 = "Pending Department Head"
PENDING_PO_TIER_1 = "Pending Accounts Review"
PENDING_TIER_2 = "Pending Board Member"
PENDING_TIER_3 = "Pending Board Chair"

PENDING_STATES = {
	PENDING_EXPENSE_TIER_1,
	PENDING_PO_TIER_1,
	PENDING_TIER_2,
	PENDING_TIER_3,
	PENDING_ROUTER_STATE,
}

ESCALATION_TRANSITIONS = {
	(PENDING_EXPENSE_TIER_1, PENDING_TIER_2),
	(PENDING_PO_TIER_1, PENDING_TIER_2),
	(PENDING_TIER_2, PENDING_TIER_3),
}

ACCOUNTING_WORKFLOW_DOCTYPES = ("Expense Claim", "Purchase Order")


def get_amount_field(doctype):
	return "total_claimed_amount" if doctype == "Expense Claim" else "grand_total"


def get_requester_user(doc):
	if doc.doctype == "Expense Claim" and doc.get("employee"):
		user = frappe.db.get_value("Employee", doc.employee, "user_id")
		if user:
			return user
	return doc.owner


def get_user_roles(user):
	if not user:
		return set()
	return set(frappe.get_roles(user))


def is_department_head_user(user):
	if not user:
		return False
	if ROLE_DEPT_HEAD in get_user_roles(user):
		return True
	return bool(
		frappe.db.exists("Department", {"department_head": user, "name": ["!=", "All Departments"]})
	)


def get_department_head_user(department):
	if not department:
		return None
	return frappe.db.get_value("Department", department, "department_head")


def get_amount_approval_level(doc):
	settings = get_accounting_settings()
	amount = frappe.utils.flt(doc.get(get_amount_field(doc.doctype)) or 0)
	tier_1 = frappe.utils.flt(settings.tier_1_limit or 2000)
	tier_2 = frappe.utils.flt(settings.tier_2_limit or 10000)

	if amount <= tier_1:
		return 1
	if amount <= tier_2:
		return 2
	return 3


def get_requester_minimum_level(doc):
	requester = get_requester_user(doc)
	roles = get_user_roles(requester)

	if ROLE_BOARD_CHAIR in roles:
		frappe.throw(
			_("Board Chairperson cannot create {0} requests.").format(doc.doctype),
			title=_("Not Allowed"),
		)

	if ROLE_BOARD_MEMBER in roles:
		return 2

	if is_department_head_user(requester):
		return 2

	return 1


def get_effective_approval_level(doc):
	return max(get_amount_approval_level(doc), get_requester_minimum_level(doc))


def get_pending_state_for_level(doctype, level):
	if level == 1:
		return PENDING_EXPENSE_TIER_1 if doctype == "Expense Claim" else PENDING_PO_TIER_1
	if level == 2:
		return PENDING_TIER_2
	return PENDING_TIER_3


def route_pending_workflow_state(doc):
	if doc.workflow_state != PENDING_ROUTER_STATE:
		return

	level = get_effective_approval_level(doc)
	doc.workflow_state = get_pending_state_for_level(doc.doctype, level)


def assign_expense_approver(doc):
	if doc.doctype != "Expense Claim" or not doc.get("employee"):
		return

	department = frappe.db.get_value("Employee", doc.employee, "department")
	dept_head = get_department_head_user(department)
	if dept_head:
		doc.expense_approver = dept_head


def validate_escalation_reason(doc):
	previous = doc.get_doc_before_save()
	if not previous:
		return

	transition = (previous.workflow_state, doc.workflow_state)
	if transition not in ESCALATION_TRANSITIONS:
		return

	if not (doc.get("escalation_reason") or "").strip():
		frappe.throw(_("A reason is required when escalating approval."))


def validate_expense_claim_receipts(doc):
	if doc.doctype != "Expense Claim":
		return

	if doc.workflow_state in (None, "", "Draft", "Rejected"):
		return

	if doc.is_new():
		frappe.throw(_("Save the expense claim and attach receipts before submitting."))

	if not frappe.db.exists(
		"File",
		{"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
	):
		frappe.throw(_("Attach at least one receipt before submitting the expense claim."))


def sync_approval_status_from_workflow(doc):
	"""Workflow update_field cannot set permlevel-1 fields for approver roles."""
	status_map = {"Approved": "Approved", "Rejected": "Rejected"}
	workflow_status = status_map.get(doc.workflow_state)
	if workflow_status:
		doc.approval_status = workflow_status


def sync_expense_claim_approval_status_before_submit(doc, method=None):
	if doc.doctype == "Expense Claim":
		sync_approval_status_from_workflow(doc)


def before_accounting_document_save(doc, method=None):
	if doc.doctype not in ACCOUNTING_WORKFLOW_DOCTYPES:
		return

	doc.approval_level = get_effective_approval_level(doc)
	assign_expense_approver(doc)
	validate_escalation_reason(doc)
	validate_expense_claim_receipts(doc)
	if doc.doctype == "Expense Claim":
		sync_approval_status_from_workflow(doc)


def on_accounting_workflow_state_change(doc, method=None):
	"""Send email alert when routed to a pending approval state."""
	if doc.doctype not in ACCOUNTING_WORKFLOW_DOCTYPES:
		return

	if doc.workflow_state not in PENDING_STATES - {PENDING_ROUTER_STATE}:
		return

	previous = doc.get_doc_before_save()
	if previous and previous.workflow_state == doc.workflow_state:
		return

	notify_pending_approvers(doc)


def notify_pending_approvers(doc):
	recipients = get_pending_approver_emails(doc)
	if not recipients:
		return

	subject = _("Approval required: {0} {1}").format(doc.doctype, doc.name)
	message = _("{0} {1} is awaiting your approval at stage: {2}.").format(
		doc.doctype,
		doc.name,
		doc.workflow_state,
	)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		now=True,
	)


def get_pending_approver_emails(doc):
	if doc.workflow_state == PENDING_EXPENSE_TIER_1 and doc.get("expense_approver"):
		return _user_emails([doc.expense_approver])

	if doc.workflow_state == PENDING_PO_TIER_1:
		return _role_user_emails([ROLE_ACCOUNTS_MANAGER])

	if doc.workflow_state == PENDING_TIER_2:
		return _role_user_emails([ROLE_BOARD_MEMBER])

	if doc.workflow_state == PENDING_TIER_3:
		return _role_user_emails([ROLE_BOARD_CHAIR])

	return []


def _user_emails(users):
	emails = []
	for user in users:
		if not user:
			continue
		email = frappe.db.get_value("User", user, "email")
		if email:
			emails.append(email)
	return emails


def _role_user_emails(roles):
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", roles], "parenttype": "User", "parent": ["!=", "Guest"]},
		pluck="parent",
	)
	return _user_emails(users)
