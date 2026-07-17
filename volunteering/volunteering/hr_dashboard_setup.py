"""Create restricted HR Accountability workspaces and shortcuts.

Existing workspaces are never overwritten (content/links persist across deploys).
"""

from __future__ import annotations

import json

import frappe

WORKSPACE = "HR Accountability"
RESTRICTED_ROLES = ("HR Manager", "System Manager")


def ensure_hr_dashboards():
	try:
		_ensure_workspace()
		_ensure_shortcuts()
	except Exception:
		frappe.log_error(title="HR dashboard setup failed", message=frappe.get_traceback())


def _ensure_workspace():
	name = frappe.db.get_value("Workspace", {"label": WORKSPACE}, "name") or frappe.db.get_value(
		"Workspace", {"title": WORKSPACE}, "name"
	)

	if name:
		_ensure_roles_only(name)
		return

	ws = frappe.new_doc("Workspace")
	ws.label = WORKSPACE
	ws.title = WORKSPACE
	ws.module = "Volunteering"
	ws.icon = "hr"
	ws.public = 1
	ws.for_user = None
	ws.content = json.dumps(_workspace_content())
	for role in RESTRICTED_ROLES:
		ws.append("roles", {"role": role})
	_apply_default_links(ws)
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.flags.ignore_validate = True
	ws.insert(ignore_permissions=True)


def _ensure_roles_only(name: str):
	"""Add missing restricted roles without touching content or links."""
	ws = frappe.get_doc("Workspace", name)
	existing = {row.role for row in (ws.roles or [])}
	missing = [role for role in RESTRICTED_ROLES if role not in existing]
	if not missing:
		return

	for role in missing:
		ws.append("roles", {"role": role})
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.flags.ignore_validate = True
	ws.save(ignore_permissions=True)


def _workspace_content():
	return [
		{
			"id": "hr_header",
			"type": "header",
			"data": {"text": '<span class="h4">HR Dashboard</span>', "col": 12},
		},
		{"id": "hr_spacer", "type": "spacer", "data": {"col": 12}},
		{
			"id": "mgmt_header",
			"type": "header",
			"data": {"text": '<span class="h4">Management Dashboard</span>', "col": 12},
		},
		{
			"id": "well_header",
			"type": "header",
			"data": {
				"text": '<span class="h4">Wellness Dashboard (informational)</span>',
				"col": 12,
			},
		},
	]


def _apply_default_links(ws):
	desired = [
		{"label": "Daily Work Log", "link_type": "DocType", "link_to": "Daily Work Log", "type": "Link"},
		{
			"label": "Attendance Regularization Request",
			"link_type": "DocType",
			"link_to": "Attendance Regularization Request",
			"type": "Link",
		},
		{"label": "Manager Note", "link_type": "DocType", "link_to": "Manager Note", "type": "Link"},
		{"label": "Attendance", "link_type": "DocType", "link_to": "Attendance", "type": "Link"},
		{"label": "Leave Application", "link_type": "DocType", "link_to": "Leave Application", "type": "Link"},
		{
			"label": "Missing Daily Logs Report",
			"link_type": "Report",
			"link_to": "Missing Daily Logs Report",
			"type": "Link",
			"is_query_report": 1,
		},
	]

	ws.links = []
	ws.append("links", {"label": "HR Accountability", "type": "Card Break"})
	for row in desired:
		if row.get("link_type") == "DocType" and not frappe.db.exists("DocType", row["link_to"]):
			continue
		if row.get("link_type") == "Report" and not frappe.db.exists("Report", row["link_to"]):
			continue
		ws.append("links", row)


def _ensure_shortcuts():
	cards = [
		{
			"name": "HR Half Days (MTD)",
			"label": "Half Days (This Month)",
			"document_type": "Attendance",
			"function": "Count",
			"filters_json": json.dumps(
				[["Attendance", "status", "=", "Half Day"], ["Attendance", "docstatus", "=", 1]]
			),
			"stats_time_interval": "Monthly",
		},
		{
			"name": "HR Open Leave Applications",
			"label": "Pending Leave Approvals",
			"document_type": "Leave Application",
			"function": "Count",
			"filters_json": json.dumps(
				[["Leave Application", "status", "=", "Open"], ["Leave Application", "docstatus", "=", 0]]
			),
		},
		{
			"name": "HR Open Regularizations",
			"label": "Open Regularization Requests",
			"document_type": "Attendance Regularization Request",
			"function": "Count",
			"filters_json": json.dumps(
				[
					["Attendance Regularization Request", "status", "=", "Open"],
					["Attendance Regularization Request", "docstatus", "=", 0],
				]
			),
		},
	]

	for card in cards:
		if frappe.db.exists("Number Card", {"label": card["label"]}):
			continue
		if not frappe.db.exists("DocType", card["document_type"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Number Card",
				"name": card["name"],
				"label": card["label"],
				"document_type": card["document_type"],
				"function": card["function"],
				"filters_json": card["filters_json"],
				"is_public": 0,
				"stats_time_interval": card.get("stats_time_interval") or "Daily",
				"show_percentage_stats": 0,
			}
		)
		doc.insert(ignore_permissions=True)
