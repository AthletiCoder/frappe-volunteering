"""Create / rebuild My Work workspace + slim sidebar (HR self-service)."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "My Work"
SIDEBAR_NAME = "My Work"
LEGACY_WORKSPACE_NAMES = ("Quick Links", "Staff Hub", "Employee Hub")
LEGACY_SIDEBAR_NAMES = ("Quick Links", "Staff Hub", "Employee Hub")

# Self-service filters — scoped to the signed-in employee (frappe.boot.employee)
DWL_PENDING_FILTER = (
	'[["Daily Work Log","employee","=",frappe.boot.employee],'
	'["Daily Work Log","docstatus","=",1],'
	'["Daily Work Log","status","!=","Reviewed"]]'
)
AR_SELF_FILTER = (
	'[["Attendance Request","employee","=",frappe.boot.employee],'
	'["Attendance Request","docstatus","=",0]]'
)
LEAVE_SELF_FILTER = (
	'[["Leave Application","employee","=",frappe.boot.employee],'
	'["Leave Application","status","=","Open"],'
	'["Leave Application","docstatus","=",0]]'
)
ATTENDANCE_SELF_FILTER = '[["Attendance","employee","=",frappe.boot.employee]]'
ARR_PENDING_FILTER = (
	'[["Attendance Regularization Request","employee","=",frappe.boot.employee],'
	'["Attendance Regularization Request","docstatus","=",0]]'
)

# Approver queues — others awaiting this user (not own requests)
LEAVE_PENDING_FILTER = (
	'[["Leave Application","leave_approver","=",frappe.session.user],'
	'["Leave Application","employee","!=",frappe.boot.employee],'
	'["Leave Application","status","=","Open"],'
	'["Leave Application","docstatus","=",0]]'
)
# WFH: manager submits reportees' drafts; permission already limits to reports_to.
# Exclude own drafts so Self Service and Awaiting my Approval don't overlap.
ATTENDANCE_REQUEST_APPROVER_FILTER = (
	'[["Attendance Request","docstatus","=",0],'
	'["Attendance Request","employee","!=",frappe.boot.employee]]'
)

# Friendly labels (shortcut cards) → DocType
SELF_SERVICE_SHORTCUTS = (
	{
		"label": "Track my Work",
		"link_to": "Daily Work Log",
		"color": "Blue",
		"stats_filter": DWL_PENDING_FILTER,
	},
	{
		"label": "Work from Home",
		"link_to": "Attendance Request",
		"color": "Blue",
		"stats_filter": AR_SELF_FILTER,
	},
	{
		"label": "Apply for Leave",
		"link_to": "Leave Application",
		"color": "Blue",
		"stats_filter": LEAVE_SELF_FILTER,
	},
	{
		"label": "Attendance History",
		"link_to": "Attendance",
		"color": "Gray",
		"stats_filter": ATTENDANCE_SELF_FILTER,
	},
	{
		"label": "Change Attendance",
		"link_to": "Attendance Regularization Request",
		"color": "Blue",
		"stats_filter": ARR_PENDING_FILTER,
	},
)

APPROVER_SHORTCUTS = (
	{
		"label": "Leave Applications",
		"link_to": "Leave Application",
		"color": "Orange",
		"stats_filter": LEAVE_PENDING_FILTER,
	},
	{
		"label": "Work from Home Requests",
		"link_to": "Attendance Request",
		"color": "Orange",
		"stats_filter": ATTENDANCE_REQUEST_APPROVER_FILTER,
	},
)

# Legacy labels to strip
LEGACY_PENDING_LABELS = (
	"Leaves Pending My Approval",
	"Pending Leave Approval",
	"Attendance Requests to Submit",
	"For Approvers",
	"Daily Work Log",
	"Attendance Request",
	"Leave Application",
	"Attendance",
	"Attendance Regularization Request",
)


def ensure_my_work():
	"""Rename legacy hubs, rebuild My Work workspace; drop redundant sidebar."""
	try:
		_delete_legacy_quick_links_workspace()
		_rename_legacy_workspace()
		_ensure_workspace_once()
		_rebuild_workspace()
		_ensure_minimal_sidebar()
	except Exception:
		frappe.log_error(title="My Work setup failed", message=frappe.get_traceback())


ensure_quick_links = ensure_my_work
ensure_staff_hub = ensure_my_work
ensure_employee_hub = ensure_my_work


def _delete_legacy_quick_links_workspace():
	if not _workspace_exists(WORKSPACE_NAME):
		return
	for legacy in LEGACY_WORKSPACE_NAMES:
		found = (
			frappe.db.exists("Workspace", legacy)
			or frappe.db.get_value("Workspace", {"label": legacy}, "name")
		)
		if found and found != WORKSPACE_NAME:
			frappe.delete_doc("Workspace", found, force=True, ignore_permissions=True)


def _workspace_exists(name: str = WORKSPACE_NAME) -> bool:
	return bool(
		frappe.db.exists("Workspace", name)
		or frappe.db.get_value("Workspace", {"label": name}, "name")
		or frappe.db.get_value("Workspace", {"title": name}, "name")
	)


def _find_legacy_workspace() -> str | None:
	for legacy_name in LEGACY_WORKSPACE_NAMES:
		found = (
			frappe.db.exists("Workspace", legacy_name)
			or frappe.db.get_value("Workspace", {"label": legacy_name}, "name")
			or frappe.db.get_value("Workspace", {"title": legacy_name}, "name")
		)
		if found and found != WORKSPACE_NAME and not _workspace_exists(WORKSPACE_NAME):
			return found
	return None


def _rename_legacy_workspace() -> bool:
	legacy = _find_legacy_workspace()
	if not legacy:
		return False

	ws = frappe.get_doc("Workspace", legacy)
	ws.label = WORKSPACE_NAME
	ws.title = WORKSPACE_NAME
	ws.icon = "briefcase"
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.flags.ignore_validate = True
	ws.save(ignore_permissions=True)
	if ws.name != WORKSPACE_NAME:
		frappe.rename_doc("Workspace", ws.name, WORKSPACE_NAME, force=True, merge=False)
	return True


def _rename_legacy_sidebar():
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		for legacy in LEGACY_SIDEBAR_NAMES:
			if legacy != SIDEBAR_NAME and frappe.db.exists("Workspace Sidebar", legacy):
				frappe.delete_doc("Workspace Sidebar", legacy, force=True, ignore_permissions=True)
		return

	for legacy in LEGACY_SIDEBAR_NAMES:
		if not frappe.db.exists("Workspace Sidebar", legacy):
			continue
		sidebar = frappe.get_doc("Workspace Sidebar", legacy)
		sidebar.title = SIDEBAR_NAME
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)
		if sidebar.name != SIDEBAR_NAME:
			frappe.rename_doc(
				"Workspace Sidebar", sidebar.name, SIDEBAR_NAME, force=True, merge=False
			)
		return


def _ensure_workspace_once():
	if _workspace_exists():
		return
	payload = _get_workspace_payload()
	workspace = frappe.get_doc(payload)
	workspace.flags.ignore_links = True
	workspace.insert(ignore_permissions=True)


def _rebuild_workspace():
	"""Point the legacy hub at SPA Home — no duplicated shortcut cards."""
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	from volunteering.volunteering.home_service import apply_moved_to_home_workspace

	ws = frappe.get_doc("Workspace", name)
	ws.set("roles", [])
	for role in ("Employee", "HR User", "HR Manager", "System Manager", "Leave Approver"):
		if frappe.db.exists("Role", role):
			ws.append("roles", {"role": role})
	apply_moved_to_home_workspace(ws, WORKSPACE_NAME)


def _ensure_minimal_sidebar():
	from volunteering.volunteering.home_service import ensure_home_sidebar

	ensure_home_sidebar(SIDEBAR_NAME, "briefcase", LEGACY_SIDEBAR_NAMES)


def _doctype_item(doctype, icon, label=None):
	return {
		"type": "Link",
		"label": label or doctype,
		"link_to": doctype,
		"link_type": "DocType",
		"icon": icon,
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _get_workspace_payload() -> dict:
	workspace_path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "my_work", "my_work.json"
	)
	with open(workspace_path, encoding="utf-8") as handle:
		return json.load(handle)
