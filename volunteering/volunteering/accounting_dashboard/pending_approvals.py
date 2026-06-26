import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import flt, formatdate, get_datetime, now_datetime, time_diff_in_hours

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTING_APPROVAL_DOCTYPES
from volunteering.volunteering.approval_routing import PENDING_STATES, get_amount_field


@frappe.whitelist()
def get_pending_approvals():
	"""Open workflow actions for accounting documents the current user can act on."""
	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	actions = _fetch_pending_rows()
	return [_enrich_action(row, user, roles) for row in actions if _can_user_act(row, user, roles)]


def _fetch_pending_rows():
	"""Merge Workflow Action rows with documents in pending states.

	Workflow Action rows alone miss tier-1 expense claims because the
	expense_approver transition condition is evaluated at submit time.
	"""
	by_key = {}
	for row in _fetch_open_workflow_actions():
		row = frappe._dict(row)
		by_key[(row.reference_doctype, row.reference_name)] = row
	for row in _fetch_pending_accounting_documents():
		row = frappe._dict(row)
		key = (row.reference_doctype, row.reference_name)
		if key not in by_key:
			by_key[key] = row
	return list(by_key.values())


def _fetch_open_workflow_actions():
	WorkflowAction = frappe.qb.DocType("Workflow Action")

	query = (
		frappe.qb.from_(WorkflowAction)
		.select(
			WorkflowAction.name.as_("workflow_action"),
			WorkflowAction.reference_doctype,
			WorkflowAction.reference_name,
			WorkflowAction.workflow_state,
			WorkflowAction.modified,
		)
		.where(WorkflowAction.status == "Open")
		.where(WorkflowAction.reference_doctype.isin(list(ACCOUNTING_APPROVAL_DOCTYPES)))
		.orderby(WorkflowAction.modified, order=Order.desc)
	)

	return query.run(as_dict=True)


def _fetch_pending_accounting_documents():
	rows = []
	for doctype in ACCOUNTING_APPROVAL_DOCTYPES:
		if not frappe.db.table_exists(doctype):
			continue
		if not frappe.db.has_column(doctype, "workflow_state"):
			continue

		docs = frappe.get_all(
			doctype,
			filters={
				"workflow_state": ["in", list(PENDING_STATES)],
				"docstatus": ["!=", 2],
			},
			fields=["name", "workflow_state", "modified"],
			order_by="modified desc",
		)
		for doc in docs:
			rows.append(
				{
					"workflow_action": None,
					"reference_doctype": doctype,
					"reference_name": doc.name,
					"workflow_state": doc.workflow_state,
					"modified": doc.modified,
				}
			)
	return rows


def _can_user_act(row, user, roles):
	if user == "Administrator":
		return True

	previous_user = frappe.session.user
	try:
		frappe.set_user(user)
		doc = frappe.get_doc(row.reference_doctype, row.reference_name)
		for transition in frappe.model.workflow.get_transitions(doc):
			transition = frappe._dict(transition)
			if transition.allowed not in roles:
				continue
			if not frappe.model.workflow.has_approval_access(user, doc, transition):
				continue
			if transition.condition and not frappe.model.workflow.is_transition_condition_satisfied(
				transition, doc
			):
				continue
			return True
		return False
	except frappe.PermissionError:
		return False
	finally:
		frappe.set_user(previous_user)


def _available_actions(doctype, name, user, roles):
	previous_user = frappe.session.user
	try:
		frappe.set_user(user)
		doc = frappe.get_doc(doctype, name)
		actions = []
		for transition in frappe.model.workflow.get_transitions(doc):
			transition = frappe._dict(transition)
			if transition.allowed not in roles:
				continue
			if not frappe.model.workflow.has_approval_access(user, doc, transition):
				continue
			if transition.condition and not frappe.model.workflow.is_transition_condition_satisfied(
				transition, doc
			):
				continue
			actions.append(transition.action)
		return sorted(set(actions))
	except frappe.PermissionError:
		return []
	finally:
		frappe.set_user(previous_user)


def _enrich_action(row, user, roles):
	fields = ["owner", "project", "company", "modified"]
	amount_field = get_amount_field(row.reference_doctype)
	fields.append(amount_field)

	if row.reference_doctype == "Expense Claim":
		fields.extend(["employee", "expense_approver"])
	elif row.reference_doctype in ("Purchase Order", "Purchase Invoice"):
		fields.append("supplier")

	doc = frappe.db.get_value(
		row.reference_doctype,
		row.reference_name,
		fields,
		as_dict=True,
	)
	if not doc:
		return row

	amount_field = get_amount_field(row.reference_doctype)
	amount = flt(doc.get(amount_field))
	modified = doc.modified or row.modified
	age_hours = time_diff_in_hours(now_datetime(), get_datetime(modified))

	requester = doc.owner
	if row.reference_doctype == "Expense Claim" and doc.get("employee"):
		requester = frappe.db.get_value("Employee", doc.employee, "user_id") or doc.owner

	available_actions = _available_actions(row.reference_doctype, row.reference_name, user, roles)

	row.update(
		{
			"amount": amount,
			"project": doc.project,
			"company": doc.company,
			"requester": requester,
			"employee": doc.get("employee"),
			"supplier": doc.get("supplier"),
			"expense_approver": doc.get("expense_approver"),
			"age_hours": age_hours,
			"age_label": _format_age(age_hours),
			"modified": modified,
			"modified_label": formatdate(modified),
			"available_actions": available_actions,
			"route": f"/app/{frappe.scrub(row.reference_doctype)}/{row.reference_name}",
		}
	)
	return row


def _format_age(hours):
	if hours < 24:
		return _("{0} hours").format(int(hours))
	days = int(hours // 24)
	return _("{0} days").format(days)
