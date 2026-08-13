# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.authority import (
	BOARD_OF_DIRECTORS,
	LEGACY_ROLE_BOARD_CHAIR,
	LEGACY_ROLE_BOARD_MEMBER,
	LEGACY_ROLE_DEPT_HEAD,
	LEGACY_ROLE_EXEC_BOARD,
	LEGACY_ROLE_EXEC_CHAIR,
	get_employee_for_user,
	get_grade_for_employee,
)
from volunteering.volunteering.authority import (
	get_fallback_board_approver as _authority_fallback_board_approver,
)
from volunteering.volunteering.authority import (
	is_department_head_user as _authority_is_department_head_user,
)
from volunteering.volunteering.authority import (
	user_has_board_of_directors,
	user_has_executive_board,
)
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
	grade_can_approve,
)

ROLE_BOARD_CHAIR = LEGACY_ROLE_BOARD_CHAIR
ROLE_BOARD_MEMBER = LEGACY_ROLE_BOARD_MEMBER
ROLE_DEPT_HEAD = LEGACY_ROLE_DEPT_HEAD
ROLE_ACCOUNTS_MANAGER = "Accounts Manager"
ROLE_EXEC_BOARD = LEGACY_ROLE_EXEC_BOARD
ROLE_EXEC_CHAIR = LEGACY_ROLE_EXEC_CHAIR

PENDING_ROUTER_STATE = "Pending"
PENDING_APPROVAL = "Pending Approval"

# Legacy tier states (kept for docs already in flight / fallback mode)
PENDING_EXPENSE_TIER_1 = "Pending Department Head"
PENDING_PO_TIER_1 = "Pending Accounts Review"
PENDING_TIER_2 = "Pending Board Member"
PENDING_TIER_3 = "Pending Board Chair"

PENDING_STATES = {
	PENDING_APPROVAL,
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

ACCOUNTING_WORKFLOW_DOCTYPES = ("Expense Claim", "Purchase Order", "Employee Advance")

AMOUNT_FIELDS = {
	"Expense Claim": "total_claimed_amount",
	"Purchase Order": "grand_total",
	"Purchase Invoice": "grand_total",
	"Employee Advance": "advance_amount",
}


def use_grade_approval(settings=None):
	"""Grade + Reports To routing. Honours the legacy flag while sites migrate."""
	settings = settings or get_accounting_settings()
	return bool(settings.get("use_grade_approval") or settings.get("use_designation_approval"))


# Legacy alias kept for call sites / tests still on the old name.
use_designation_approval = use_grade_approval


def get_amount_field(doctype):
	return AMOUNT_FIELDS.get(doctype, "grand_total")


def get_document_amount(doc):
	return flt(doc.get(get_amount_field(doc.doctype)) or 0)


def get_requester_user(doc):
	if doc.doctype in ("Expense Claim", "Employee Advance") and doc.get("employee"):
		user = frappe.db.get_value("Employee", doc.employee, "user_id")
		if user:
			return user
	return doc.owner


def get_requester_employee(doc):
	if doc.doctype in ("Expense Claim", "Employee Advance") and doc.get("employee"):
		return doc.employee
	return frappe.db.get_value("Employee", {"user_id": doc.owner}, "name")


def is_department_head_user(user):
	return _authority_is_department_head_user(user)


def get_department_head_user(department):
	if not department:
		return None
	return frappe.db.get_value("Department", department, "department_head")


def get_approval_band_for_employee(employee):
	"""Employee Grade carries the limits; fall back to Designation pre-migration."""
	if not employee:
		return None
	return get_grade_for_employee(employee) or frappe.db.get_value(
		"Employee", employee, "designation"
	)


def get_approval_band_for_user(user):
	return get_approval_band_for_employee(get_employee_for_user(user))


# Legacy alias — limits moved from Designation to Employee Grade.
get_designation_for_user = get_approval_band_for_user


def get_reports_to_user(employee):
	"""Return user_id of the employee's reports_to manager."""
	if not employee:
		return None
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	if not manager:
		return None
	return frappe.db.get_value("Employee", manager, "user_id")


def walk_approval_chain(employee, amount, start_after_employee=None):
	"""
	Walk reports_to upward from employee. Yield (user, manager_employee, grade, can_approve).
	If start_after_employee is set, skip that manager and yield subsequent ones (escalation).
	"""
	settings = get_accounting_settings()
	seen = set()
	current = employee
	skip_until_passed = start_after_employee

	while current and current not in seen:
		seen.add(current)
		manager = frappe.db.get_value("Employee", current, "reports_to")
		if not manager or manager in seen:
			break

		if skip_until_passed:
			if manager == skip_until_passed:
				skip_until_passed = None
			current = manager
			continue

		user = frappe.db.get_value("Employee", manager, "user_id")
		grade = get_approval_band_for_employee(manager)
		can_approve = False
		if grade == BOARD_OF_DIRECTORS:
			can_approve = True
		elif grade:
			can_approve = grade_can_approve(grade, amount, settings)
		yield user, manager, grade, can_approve
		current = manager


def find_first_approver(employee, amount, start_after_employee=None):
	"""Return first manager user in chain (prefer one who can approve; else next manager)."""
	first = None
	for user, emp, grade, can_approve in walk_approval_chain(
		employee, amount, start_after_employee=start_after_employee
	):
		if not user:
			continue
		if first is None:
			first = user
		if can_approve:
			return user
	if first:
		return first
	return get_fallback_board_approver()


def get_fallback_board_approver():
	return _authority_fallback_board_approver()


def user_can_approve_amount(user, amount):
	if not user:
		return False
	if user_has_board_of_directors(user):
		return True
	return grade_can_approve(get_approval_band_for_user(user), amount)


def assign_pending_approver(doc):
	"""Set pending_approver from reports_to chain. No self-approval."""
	requester = get_requester_user(doc)
	employee = get_requester_employee(doc)
	amount = get_document_amount(doc)

	if not employee:
		doc.pending_approver = get_fallback_board_approver()
		return

	approver = find_first_approver(employee, amount)
	if approver and approver == requester:
		# Skip self — escalate one more hop
		emp = get_employee_for_user(approver)
		approver = find_first_approver(employee, amount, start_after_employee=emp) if emp else get_fallback_board_approver()

	doc.pending_approver = approver or get_fallback_board_approver()


def escalate_to_next_approver(doc):
	"""Move pending_approver to next person up the chain."""
	requester_emp = get_requester_employee(doc)
	current_user = doc.get("pending_approver") or frappe.session.user
	current_emp = get_employee_for_user(current_user)
	amount = get_document_amount(doc)

	next_approver = find_first_approver(
		requester_emp, amount, start_after_employee=current_emp
	)
	if not next_approver or next_approver == current_user:
		next_approver = get_fallback_board_approver()

	if not next_approver or next_approver == current_user:
		frappe.throw(_("No higher approver found in the reporting chain."))

	doc.pending_approver = next_approver


# --- Legacy tier helpers (fallback when grade approval is off) ---


def get_amount_approval_level(doc):
	settings = get_accounting_settings()
	amount = get_document_amount(doc)
	tier_1 = flt(settings.tier_1_limit or 2000)
	tier_2 = flt(settings.tier_2_limit or 10000)

	if amount <= tier_1:
		return 1
	if amount <= tier_2:
		return 2
	return 3


def get_requester_minimum_level(doc):
	requester = get_requester_user(doc)

	if user_has_board_of_directors(requester):
		frappe.throw(
			_("Board of Directors cannot create {0} requests.").format(doc.doctype),
			title=_("Not Allowed"),
		)

	if user_has_executive_board(requester):
		return 2

	if is_department_head_user(requester):
		return 2

	return 1


def get_effective_approval_level(doc):
	return max(get_amount_approval_level(doc), get_requester_minimum_level(doc))


def get_pending_state_for_level(doctype, level):
	if use_grade_approval():
		return PENDING_APPROVAL
	if level == 1:
		return PENDING_EXPENSE_TIER_1 if doctype == "Expense Claim" else PENDING_PO_TIER_1
	if level == 2:
		return PENDING_TIER_2
	return PENDING_TIER_3


def route_pending_workflow_state(doc):
	if doc.workflow_state != PENDING_ROUTER_STATE:
		return
	if use_grade_approval():
		doc.workflow_state = PENDING_APPROVAL
		return
	level = get_effective_approval_level(doc)
	doc.workflow_state = get_pending_state_for_level(doc.doctype, level)


def assign_expense_approver(doc):
	if doc.doctype != "Expense Claim" or not doc.get("employee"):
		return

	if use_grade_approval() and doc.get("pending_approver"):
		doc.expense_approver = doc.pending_approver
		return

	department = frappe.db.get_value("Employee", doc.employee, "department")
	dept_head = get_department_head_user(department)
	if dept_head:
		doc.expense_approver = dept_head


def validate_no_self_approval(doc):
	if doc.workflow_state not in ("Approved",):
		return
	previous = doc.get_doc_before_save()
	if not previous or previous.workflow_state == "Approved":
		return
	requester = get_requester_user(doc)
	if frappe.session.user == requester:
		frappe.throw(_("You cannot approve your own {0}.").format(doc.doctype))


def validate_approver_authority(doc):
	"""Block Approve when pending approver's grade limit is below amount."""
	previous = doc.get_doc_before_save()
	if not previous:
		return
	if doc.workflow_state != "Approved" or previous.workflow_state == "Approved":
		return
	if not use_grade_approval():
		return

	amount = get_document_amount(doc)
	user = frappe.session.user
	if user != (doc.get("pending_approver") or previous.get("pending_approver")):
		# Board chair override path still allowed if they have unlimited
		if not user_can_approve_amount(user, amount):
			frappe.throw(
				_("Only the assigned approver ({0}) may approve this document.").format(
					previous.get("pending_approver") or _("unknown")
				)
			)
		return

	if not user_can_approve_amount(user, amount):
		frappe.throw(
			_(
				"Your grade approval limit is below {0}. "
				"Reject or Escalate to a higher authority."
			).format(frappe.format_value(amount, "Currency"))
		)


def validate_escalation_reason(doc):
	previous = doc.get_doc_before_save()
	if not previous:
		return

	# Grade mode: escalate keeps Pending Approval but pending_approver changes
	if use_grade_approval():
		if (
			previous.workflow_state == PENDING_APPROVAL
			and doc.workflow_state == PENDING_APPROVAL
			and doc.get("pending_approver")
			and previous.get("pending_approver")
			and doc.pending_approver != previous.pending_approver
		):
			if not (doc.get("escalation_reason") or "").strip():
				frappe.throw(_("A reason is required when escalating approval."))
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

	# Always block Board of Directors create (grade and legacy tier modes)
	get_requester_minimum_level(doc)

	if use_grade_approval():
		doc.approval_level = 1
		if doc.workflow_state in (PENDING_APPROVAL, PENDING_ROUTER_STATE):
			if not doc.get("pending_approver"):
				assign_pending_approver(doc)
		elif doc.workflow_state in (None, "", "Draft", "Rejected"):
			# Pre-compute so Submit lands with an approver
			assign_pending_approver(doc)
	else:
		doc.approval_level = get_effective_approval_level(doc)

	assign_expense_approver(doc)
	validate_escalation_reason(doc)
	validate_expense_claim_receipts(doc)
	validate_no_self_approval(doc)
	validate_approver_authority(doc)
	if doc.doctype == "Expense Claim":
		sync_approval_status_from_workflow(doc)


def before_accounting_document_submit(doc, method=None):
	"""Re-check the approval guards on submit.

	Approve sets docstatus=1 and calls submit(), which skips before_save — so
	without this the assigned approver could clear an amount above their
	grade limit instead of escalating.
	"""
	if doc.doctype not in ACCOUNTING_WORKFLOW_DOCTYPES:
		return

	validate_no_self_approval(doc)
	validate_approver_authority(doc)


def on_accounting_workflow_state_change(doc, method=None):
	"""Send email alert when routed to a pending approval state."""
	if doc.doctype not in ACCOUNTING_WORKFLOW_DOCTYPES:
		return

	if doc.workflow_state not in PENDING_STATES - {PENDING_ROUTER_STATE}:
		return

	previous = doc.get_doc_before_save()
	if previous and previous.workflow_state == doc.workflow_state:
		# Still notify if pending_approver changed (escalation)
		if not (
			use_grade_approval()
			and previous.get("pending_approver") != doc.get("pending_approver")
		):
			return

	if use_grade_approval() and doc.workflow_state == PENDING_APPROVAL and not doc.get(
		"pending_approver"
	):
		assign_pending_approver(doc)

	notify_pending_approvers(doc)


def notify_pending_approvers(doc):
	recipients = get_pending_approver_emails(doc)
	if not recipients:
		return

	subject = _("Approval required: {0} {1}").format(doc.doctype, doc.name)
	link = frappe.utils.get_url_to_form(doc.doctype, doc.name)
	message = _(
		'{0} <a href="{1}">{2}</a> is awaiting your approval at stage: {3}.'
	).format(doc.doctype, link, doc.name, doc.workflow_state)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		now=True,
	)


def get_pending_approver_emails(doc):
	if use_grade_approval() and doc.get("pending_approver"):
		return _user_emails([doc.pending_approver])

	if doc.workflow_state == PENDING_EXPENSE_TIER_1 and doc.get("expense_approver"):
		return _user_emails([doc.expense_approver])

	if doc.workflow_state == PENDING_PO_TIER_1:
		return _role_user_emails([ROLE_ACCOUNTS_MANAGER])

	if doc.workflow_state == PENDING_TIER_2:
		return _role_user_emails([ROLE_BOARD_MEMBER, ROLE_EXEC_BOARD])

	if doc.workflow_state == PENDING_TIER_3:
		return _role_user_emails([ROLE_BOARD_CHAIR, ROLE_EXEC_CHAIR])

	if doc.workflow_state == PENDING_APPROVAL and doc.get("pending_approver"):
		return _user_emails([doc.pending_approver])

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


@frappe.whitelist()
def escalate_document(doctype, name, escalation_reason):
	"""Escalate to next reporting manager / capable authority."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	if doc.workflow_state != PENDING_APPROVAL:
		frappe.throw(_("Document is not pending approval."))

	if frappe.session.user != doc.get("pending_approver"):
		frappe.throw(_("Only the current pending approver can escalate."))

	if not (escalation_reason or "").strip():
		frappe.throw(_("A reason is required when escalating approval."))

	amount = get_document_amount(doc)
	if use_grade_approval() and user_can_approve_amount(frappe.session.user, amount):
		frappe.throw(
			_(
				"Your grade limit covers this amount. Approve or Reject — "
				"Escalate is only when the amount exceeds your limit."
			)
		)

	doc.escalation_reason = escalation_reason
	escalate_to_next_approver(doc)
	_remove_stale_approver_share(doc)
	doc.save(ignore_permissions=True)
	notify_pending_approvers(doc)
	return doc


def _remove_stale_approver_share(doc):
	"""HRMS share_doc_with_approver deletes the outgoing approver's DocShare as
	the session user, who typically lacks DocShare delete permission. Remove it
	up front with elevated permissions so escalation doesn't crash."""
	if doc.doctype != "Expense Claim":
		return
	old_approver = frappe.db.get_value(doc.doctype, doc.name, "expense_approver")
	if not old_approver:
		return
	share = frappe.db.get_value(
		"DocShare",
		{"user": old_approver, "share_name": doc.name, "share_doctype": doc.doctype},
	)
	if share:
		frappe.delete_doc(
			"DocShare",
			share,
			ignore_permissions=True,
			force=True,
			delete_permanently=True,
			flags={"ignore_share_permission": True},
		)


@frappe.whitelist()
def get_approver_action_flags(doctype, name):
	"""Return which Review actions the current user should see."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	is_pending_approver = (
		doc.get("workflow_state") == PENDING_APPROVAL
		and doc.get("pending_approver") == frappe.session.user
	)
	if not is_pending_approver:
		return {
			"is_pending_approver": False,
			"can_approve": False,
			"can_escalate": False,
			"can_reject": False,
		}

	amount = get_document_amount(doc)
	can_approve = True
	if use_grade_approval():
		can_approve = user_can_approve_amount(frappe.session.user, amount)

	return {
		"is_pending_approver": True,
		"can_approve": can_approve,
		"can_escalate": not can_approve,
		"can_reject": True,
		"amount": amount,
	}
