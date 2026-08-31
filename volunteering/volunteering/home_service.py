# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Role-aware Home payload for the volunteering SPA."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, formatdate, format_datetime

from volunteering.volunteering.authority import get_employee_for_user, get_grade_for_user
from volunteering.volunteering.desk_routes import desk_route
from volunteering.volunteering.employee_advance_controls import (
	SETTLED_STATUSES,
	advance_residual_amount,
)
from volunteering.volunteering.home_access import classify_home_access
from volunteering.volunteering.workspace_setup import get_latest_ngo_event

HOME_URL = "/volunteering/home"
TODOS_URL = "/volunteering/todos"
ADVANCES_URL = "/volunteering/advances"
BUDGET_HEALTH_URL = "/volunteering/budget-health"
INBOX_CAP = 12
HELP_URL = "/help"

PERSONA_GREETING = {
	"employee": _("What do you need to do?"),
	"manager": _("Needs you first, then your own work."),
	"accounts": _("Pay and reconcile. Self-service is below."),
	"hr": _("People ops first."),
	"coordinator": _("Campaign snapshot, then your own work."),
	"admin": _("Organisation home."),
	"volunteer": _("This Home is for staff. Use the volunteer portal."),
}


@frappe.whitelist()
def get_home_payload():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to open Home."), frappe.PermissionError)

	roles = frappe.get_roles(user)
	employee = get_employee_for_user(user)
	grade = get_grade_for_user(user)
	flags = classify_home_access(roles, bool(employee), grade)
	full_name = frappe.db.get_value("User", user, "full_name") or user

	if not flags["allowed"]:
		return {
			"allowed": False,
			"persona": flags["persona"],
			"full_name": full_name,
			"greeting": PERSONA_GREETING["volunteer"],
			"help_url": HELP_URL,
			"nav": {"home": True, "advances": False, "volunteering": False, "budget_health": False},
			"inbox": [],
			"waiting": [],
			"waiting_count": 0,
			"resume": [],
			"todos": [],
			"todo_count": 0,
			"accounts_queues": [],
			"actions": {"time": [], "money": []},
			"status": [],
			"programs": None,
			"people": [],
			"admin": [],
			"flags": flags,
		}

	inbox = _approver_inbox(user, employee) if flags["show_approver_inbox"] else []
	accounts_queues = _accounts_queues() if flags["show_accounts"] else []
	pending = _own_pending(employee, user)
	status = _status_rows(pending)
	waiting = _compose_waiting(inbox, accounts_queues)
	resume = _employee_draft_todos(employee)
	# Legacy alias: todos = waiting only (no status aggregates / drafts).
	todos = waiting
	payload = {
		"allowed": True,
		"persona": flags["persona"],
		"full_name": full_name,
		"employee": employee,
		"greeting": PERSONA_GREETING.get(flags["persona"], PERSONA_GREETING["employee"]),
		"help_url": HELP_URL,
		"nav": {
			"home": True,
			"advances": flags["show_advances"],
			"volunteering": flags["show_programs"],
			"budget_health": flags["show_budget_health"],
		},
		"inbox": inbox,
		"waiting": waiting,
		"waiting_count": len(waiting),
		"resume": resume,
		"todos": todos,
		"todo_count": len(waiting),
		"accounts_queues": accounts_queues,
		"actions": {
			"time": _time_actions(pending) if flags["show_time"] else [],
			"money": _money_actions(pending) if flags["show_money"] else [],
		},
		"status": status,
		"programs": _programs_block() if flags["show_programs"] else None,
		"people": _people_links() if flags["show_people"] else [],
		"admin": _admin_links() if flags["show_admin"] else [],
		"flags": flags,
	}
	return payload


def _compose_waiting(inbox, accounts_queues):
	"""Decisions and pay queues only — Home triage, oldest review first."""
	waiting = []
	for item in inbox or []:
		waiting.append({**item, "bucket": "review"})
	waiting.sort(key=lambda row: row.get("modified") or row.get("raised_at") or "")
	for queue in accounts_queues or []:
		count = queue.get("count") or 0
		if not count:
			continue
		waiting.append(
			{
				"id": f"queue::{queue['id']}",
				"kind": _("Pay"),
				"title": queue["label"],
				"subtitle": _("{0} waiting").format(count),
				"route": queue["route"],
				"count": count,
				"bucket": "pay",
				"modified": "",
			}
		)
	return waiting


def _compose_todos(inbox, accounts_queues, status=None, employee=None):
	"""Deprecated combiner kept for callers; prefer _compose_waiting + drafts."""
	todos = _compose_waiting(inbox, accounts_queues)
	todos.extend(_employee_draft_todos(employee))
	for row in status or []:
		count = row.get("count") or 0
		if not count:
			continue
		todos.append(
			{
				"id": f"status::{row['id']}",
				"kind": _("Yours"),
				"title": row["label"],
				"subtitle": _("{0} open").format(count),
				"route": row["route"],
				"count": count,
				"bucket": "yours",
				"modified": "",
			}
		)
	return todos


def _employee_draft_todos(employee):
	"""Individual draft advances / claims with raised-on timestamp."""
	if not employee:
		return []
	todos = []
	for doctype, kind, amount_field in (
		("Employee Advance", _("Advance"), "advance_amount"),
		("Expense Claim", _("Claim"), "total_claimed_amount"),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		fields = ["name", "creation", "modified", amount_field]
		if frappe.db.has_column(doctype, "workflow_state"):
			fields.append("workflow_state")
		rows = frappe.get_all(
			doctype,
			filters={"employee": employee, "docstatus": 0},
			fields=fields,
			order_by="modified desc",
			limit=8,
		)
		for row in rows:
			amount = row.get(amount_field)
			subtitle_parts = [format_datetime(row.creation, "dd MMM yyyy, HH:mm")]
			if amount:
				subtitle_parts.append(frappe.format_value(flt(amount), "Currency"))
			state = row.get("workflow_state")
			if state and state != "Draft":
				subtitle_parts.append(state)
			todos.append(
				{
					"id": f"{doctype}::{row.name}",
					"kind": kind,
					"title": row.name,
					"subtitle": " · ".join(subtitle_parts),
					"route": desk_route(doctype, row.name),
					"bucket": "resume",
					"modified": str(row.modified or ""),
					"raised_at": str(row.creation or ""),
				}
			)
	return todos


def _own_pending(employee, user):
	pending = {
		"log_work": 0,
		"wfh": 0,
		"leave": 0,
		"fix_attendance": 0,
		"vendor": 0,
		"advance": 0,
		"claim": 0,
	}
	if employee:
		pending["leave"] = _safe_count(
			"Leave Application",
			{"employee": employee, "status": "Open", "docstatus": 0},
		)
		pending["wfh"] = _safe_count(
			"Attendance Request",
			{"employee": employee, "docstatus": 0},
		)
		pending["fix_attendance"] = _safe_count(
			"Attendance Regularization Request",
			{"employee": employee, "docstatus": 0},
		)
		pending["claim"] = _safe_count(
			"Expense Claim",
			{"employee": employee, "docstatus": 0},
		)
		pending["advance"] = _safe_count(
			"Employee Advance",
			{"employee": employee, "docstatus": 0},
		)
		pending["log_work"] = _safe_count(
			"Daily Work Log",
			{"employee": employee, "docstatus": 0},
		)
	if user:
		pending["vendor"] = _safe_count("Purchase Order", {"owner": user, "docstatus": 0})
	return pending


def _with_history(action, list_route, list_label, pending_key, pending):
	action["list_route"] = list_route
	action["list_label"] = list_label
	action["pending"] = (pending or {}).get(pending_key) or 0
	return action


def _time_actions(pending=None):
	pending = pending or {}
	return [
		_with_history(
			{
				"id": "log_work",
				"label": _("Track work"),
				"hint": _("Log today"),
				"route": "/desk/daily-work-log/new",
			},
			"/desk/daily-work-log",
			_("Previous work logs"),
			"log_work",
			pending,
		),
		_with_history(
			{
				"id": "wfh",
				"label": _("Request WFH"),
				"hint": _("Before you stay home"),
				"route": "/desk/attendance-request/new",
			},
			"/desk/attendance-request",
			_("Previous WFH"),
			"wfh",
			pending,
		),
		_with_history(
			{
				"id": "leave",
				"label": _("Apply for leave"),
				"hint": _("Normal or emergency"),
				"route": "/desk/leave-application/new",
			},
			"/desk/leave-application",
			_("Previous leave"),
			"leave",
			pending,
		),
		_with_history(
			{
				"id": "fix_attendance",
				"label": _("Fix attendance"),
				"hint": _("Wrong Present / Absent day"),
				"route": "/desk/attendance-regularization-request/new",
			},
			"/desk/attendance-regularization-request",
			_("Previous attendance fixes"),
			"fix_attendance",
			pending,
		),
	]


def _money_actions(pending=None):
	pending = pending or {}
	return [
		_with_history(
			{
				"id": "vendor",
				"label": _("Pay a vendor"),
				"hint": _("Preferred — organisation pays"),
				"route": "/desk/purchase-order/new",
			},
			"/desk/purchase-order",
			_("Previous purchase orders"),
			"vendor",
			pending,
		),
		_with_history(
			{
				"id": "advance",
				"label": _("Request an advance"),
				"hint": _("Float before you buy"),
				"route": "/desk/employee-advance/new",
			},
			"/desk/employee-advance",
			_("Previous advances"),
			"advance",
			pending,
		),
		_with_history(
			{
				"id": "claim",
				"label": _("Claim money back"),
				"hint": _("Only if vendor/advance was not possible"),
				"route": "/desk/expense-claim/new",
			},
			"/desk/expense-claim",
			_("Previous claims"),
			"claim",
			pending,
		),
		{
			"id": "how_to_spend",
			"label": _("How to spend"),
			"hint": _("Pick one path"),
			"route": "/help/accounts/how-to-spend",
		},
	]


def _status_rows(pending):
	rows = []
	mapping = (
		("leave", "open_leave", _("Open leave"), desk_route("Leave Application")),
		("wfh", "open_wfh", _("Open WFH"), desk_route("Attendance Request")),
		(
			"fix_attendance",
			"open_arr",
			_("Attendance fixes"),
			desk_route("Attendance Regularization Request"),
		),
	)
	for key, row_id, label, route in mapping:
		count = (pending or {}).get(key) or 0
		if not count:
			continue
		rows.append({"id": row_id, "label": label, "count": count, "route": route})
	return rows


def _approver_inbox(user, employee):
	items = []
	items.extend(_leave_inbox(user, employee))
	items.extend(_wfh_inbox(employee))
	items.extend(_pending_approver_inbox("Expense Claim", _("Claim"), user))
	items.extend(_pending_approver_inbox("Employee Advance", _("Advance"), user))
	items.extend(_pending_approver_inbox("Purchase Order", _("Purchase order"), user))
	items.sort(key=lambda row: row.get("modified") or "", reverse=True)
	return items[:INBOX_CAP]


def _leave_inbox(user, employee):
	if not frappe.db.exists("DocType", "Leave Application"):
		return []
	filters = {
		"leave_approver": user,
		"status": "Open",
		"docstatus": 0,
	}
	if employee:
		filters["employee"] = ["!=", employee]
	rows = frappe.get_all(
		"Leave Application",
		filters=filters,
		fields=["name", "employee_name", "from_date", "to_date", "modified", "leave_type"],
		order_by="modified desc",
		limit=INBOX_CAP,
	)
	out = []
	for row in rows:
		out.append(
			{
				"id": f"Leave Application::{row.name}",
				"kind": "Leave",
				"title": row.employee_name or row.name,
				"subtitle": f"{row.leave_type or ''} · {formatdate(row.from_date)} – {formatdate(row.to_date)}",
				"route": f"/desk/leave-application/{row.name}",
				"modified": str(row.modified or ""),
			}
		)
	return out


def _wfh_inbox(employee):
	if not frappe.db.exists("DocType", "Attendance Request"):
		return []
	filters = {"docstatus": 0}
	if employee:
		filters["employee"] = ["!=", employee]
	rows = frappe.get_all(
		"Attendance Request",
		filters=filters,
		fields=["name", "employee_name", "from_date", "to_date", "modified", "reason"],
		order_by="modified desc",
		limit=INBOX_CAP,
	)
	out = []
	for row in rows:
		out.append(
			{
				"id": f"Attendance Request::{row.name}",
				"kind": "WFH",
				"title": row.employee_name or row.name,
				"subtitle": f"{formatdate(row.from_date)} – {formatdate(row.to_date)}",
				"route": f"/desk/attendance-request/{row.name}",
				"modified": str(row.modified or ""),
			}
		)
	return out


def _pending_approver_inbox(doctype, kind, user):
	if not frappe.db.exists("DocType", doctype):
		return []
	if not frappe.db.has_column(doctype, "pending_approver"):
		return []
	fields = ["name", "modified", "creation"]
	if frappe.db.has_column(doctype, "employee_name"):
		fields.append("employee_name")
	if frappe.db.has_column(doctype, "supplier_name"):
		fields.append("supplier_name")
	if frappe.db.has_column(doctype, "total_claimed_amount"):
		fields.append("total_claimed_amount")
	if frappe.db.has_column(doctype, "grand_total"):
		fields.append("grand_total")
	if frappe.db.has_column(doctype, "advance_amount"):
		fields.append("advance_amount")
	rows = frappe.get_all(
		doctype,
		filters={"pending_approver": user, "docstatus": 0},
		fields=fields,
		order_by="modified desc",
		limit=INBOX_CAP,
	)
	out = []
	for row in rows:
		amount = row.get("grand_total") or row.get("total_claimed_amount") or row.get("advance_amount")
		who = row.get("employee_name") or row.get("supplier_name") or row.name
		subtitle_parts = [format_datetime(row.creation, "dd MMM yyyy, HH:mm"), row.name]
		if amount:
			subtitle_parts.append(frappe.format_value(flt(amount), "Currency"))
		out.append(
			{
				"id": f"{doctype}::{row.name}",
				"kind": kind,
				"title": who,
				"subtitle": " · ".join(subtitle_parts),
				"route": desk_route(doctype, row.name),
				"modified": str(row.modified or ""),
				"raised_at": str(row.creation or ""),
			}
		)
	return out


def _accounts_queues():
	queues = []
	reimburse = _safe_count(
		"Expense Claim",
		{"docstatus": 1, "approval_status": "Approved", "status": "Unpaid"},
	)
	vendor = _safe_count(
		"Purchase Invoice",
		{"docstatus": 1, "outstanding_amount": [">", 0]},
	)
	residual = _residual_advance_count()
	if reimburse:
		queues.append(
			{
				"id": "reimburse",
				"label": _("Claims to reimburse"),
				"count": reimburse,
				"route": "/desk/expense-claim",
			}
		)
	if vendor:
		queues.append(
			{
				"id": "vendor_pay",
				"label": _("Vendor invoices to pay"),
				"count": vendor,
				"route": "/desk/purchase-invoice",
			}
		)
	if residual:
		queues.append(
			{
				"id": "residual",
				"label": _("Advances with leftover"),
				"count": residual,
				"route": "/desk/query-report/Employee%20Advances%20with%20Residual",
			}
		)
	return queues


def _residual_advance_count():
	if not frappe.db.exists("DocType", "Employee Advance"):
		return 0
	rows = frappe.get_all(
		"Employee Advance",
		filters={"docstatus": 1, "status": ["not in", list(SETTLED_STATUSES)]},
		fields=["name", "advance_amount", "paid_amount", "claimed_amount", "return_amount", "status"],
		limit=200,
	)
	return sum(1 for row in rows if advance_residual_amount(row) > 0)


def _programs_block():
	event = get_latest_ngo_event()
	registrations = 0
	if event and frappe.db.exists("DocType", "Participation"):
		registrations = _safe_count("Participation", {"event": event})
	return {
		"event": event,
		"registrations": registrations,
		"workspace_route": "/desk/volunteering",
		"report_route": "/desk/query-report/Generic%20Event%20Participation%20Report",
	}


def _people_links():
	return [
		{
			"id": "missing_logs",
			"label": _("Missing daily logs"),
			"route": "/desk/query-report/Missing%20Daily%20Logs%20Report",
		},
		{
			"id": "regularization",
			"label": _("Attendance fixes"),
			"route": "/desk/attendance-regularization-request",
		},
		{
			"id": "attendance",
			"label": _("Attendance"),
			"route": "/desk/attendance",
		},
		{
			"id": "hr_accountability",
			"label": _("HR reports"),
			"route": "/desk/hr-accountability",
		},
	]


def _admin_links():
	return [
		{
			"id": "limits",
			"label": _("Approval & Advance Limits"),
			"route": "/desk/approval-and-advance-limits",
		},
		{
			"id": "acct_settings",
			"label": _("Accounting Settings"),
			"route": "/desk/volunteering-accounting-settings",
		},
	]


def _safe_count(doctype, filters):
	if not frappe.db.exists("DocType", doctype):
		return 0
	try:
		return frappe.db.count(doctype, filters) or 0
	except Exception:
		return 0


def moved_to_home_workspace_content(old_title):
	"""Frappe Workspace content: one Home shortcut, no duplicated cards."""
	import json

	return json.dumps(
		[
			{
				"id": "home-moved-header",
				"type": "header",
				"data": {"text": f'<span class="h4">{old_title}</span>', "col": 12},
			},
			{
				"id": "home-moved-intro",
				"type": "paragraph",
				"data": {
					"text": (
						"This hub moved to <a href='/volunteering/home'>Home</a>. "
						"Open Home for tasks, approvals, and accounts queues."
					),
					"col": 12,
				},
			},
			{
				"id": "home-moved-shortcut",
				"type": "shortcut",
				"data": {"shortcut_name": "Home", "col": 4},
			},
		]
	)


def home_workspace_shortcut():
	return spa_workspace_shortcut("Home", HOME_URL, "Blue")


def spa_workspace_shortcut(label, url, color="Blue"):
	return {
		"type": "URL",
		"label": label,
		"url": url,
		"color": color,
		"doc_view": "",
	}


def spa_workspace_shortcuts():
	return [
		spa_workspace_shortcut("Home", HOME_URL, "Blue"),
		spa_workspace_shortcut("To-do", TODOS_URL, "Orange"),
		spa_workspace_shortcut("Advance Portal", ADVANCES_URL, "Green"),
		spa_workspace_shortcut("Budget Health", BUDGET_HEALTH_URL, "Yellow"),
	]


def home_sidebar_item(icon="home"):
	return {
		"type": "Link",
		"label": "Home",
		"link_to": HOME_URL,
		"link_type": "URL",
		"icon": icon,
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def apply_moved_to_home_workspace(workspace_doc, old_title):
	"""Replace a Desk hub with a single Home shortcut."""
	workspace_doc.set("shortcuts", [])
	workspace_doc.set("links", [])
	workspace_doc.append("shortcuts", home_workspace_shortcut())
	workspace_doc.content = moved_to_home_workspace_content(old_title)
	workspace_doc.flags.ignore_links = True
	workspace_doc.flags.ignore_permissions = True
	workspace_doc.flags.ignore_validate = True
	workspace_doc.save(ignore_permissions=True)


def ensure_home_sidebar(sidebar_name, icon, legacy_names=()):
	item = home_sidebar_item(icon)
	for legacy in legacy_names:
		if legacy != sidebar_name and frappe.db.exists("Workspace Sidebar", legacy):
			frappe.delete_doc("Workspace Sidebar", legacy, force=True, ignore_permissions=True)

	if frappe.db.exists("Workspace Sidebar", sidebar_name):
		sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
		sidebar.items = []
		sidebar.append("items", item)
		sidebar.header_icon = icon
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)
		return

	frappe.get_doc(
		{
			"doctype": "Workspace Sidebar",
			"title": sidebar_name,
			"header_icon": icon,
			"items": [item],
		}
	).insert(ignore_permissions=True)
