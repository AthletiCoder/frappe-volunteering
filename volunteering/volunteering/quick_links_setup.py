"""Create-once My Work workspace + sidebar for employees (HR self-service)."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "My Work"
SIDEBAR_NAME = "My Work"
LEGACY_WORKSPACE_NAMES = ("Quick Links", "Staff Hub", "Employee Hub")
LEGACY_SIDEBAR_NAMES = ("Quick Links", "Staff Hub", "Employee Hub")

# Workspace shortcut filters (evaluated client-side with frappe.session.user)
LEAVE_PENDING_FILTER = (
	'[["Leave Application","leave_approver","=",frappe.session.user],'
	'["Leave Application","status","=","Open"],'
	'["Leave Application","docstatus","=",0]]'
)
ATTENDANCE_REQUEST_DRAFT_FILTER = (
	'[["Attendance Request","docstatus","=",0]]'
)

LEAVE_PENDING_LABEL = "Leaves Pending My Approval"
ATTENDANCE_PENDING_LABEL = "Attendance Requests to Submit"
LEGACY_PENDING_LABELS = (
	LEAVE_PENDING_LABEL,
	"Pending Leave Approval",
	"Leaves Pending My Approval",
)


def ensure_my_work():
	"""Rename legacy hubs, ensure My Work workspace + sidebar once."""
	try:
		_delete_legacy_quick_links_workspace()
		_rename_legacy_workspace()
		_rename_legacy_sidebar()
		_ensure_workspace_once()
		_ensure_attendance_request_label()
		_ensure_approver_filter_shortcuts()
		_ensure_sidebar()
	except Exception:
		frappe.log_error(title="My Work setup failed", message=frappe.get_traceback())


# Backwards-compatible aliases
ensure_quick_links = ensure_my_work
ensure_staff_hub = ensure_my_work
ensure_employee_hub = ensure_my_work


def _delete_legacy_quick_links_workspace():
	"""Remove leftover Quick Links if My Work already exists."""
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
	if ws.content:
		for old in LEGACY_WORKSPACE_NAMES:
			if old in ws.content:
				ws.content = ws.content.replace(old, WORKSPACE_NAME)
		ws.content = (ws.content or "").replace("WFH requests", "Attendance Request")
		ws.content = (ws.content or "").replace("Work From Home", "Attendance Request")
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
		for item in sidebar.items or []:
			if item.link_type == "Workspace" and item.link_to in LEGACY_WORKSPACE_NAMES:
				item.link_to = WORKSPACE_NAME
				item.label = WORKSPACE_NAME
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
	payload["links"] = [
		row
		for row in payload.get("links") or []
		if row.get("type") == "Card Break"
		or (
			row.get("link_type") == "DocType"
			and frappe.db.exists("DocType", row.get("link_to"))
		)
		or (
			row.get("link_type") == "Report"
			and frappe.db.exists("Report", row.get("link_to"))
		)
	]
	payload["shortcuts"] = [
		row
		for row in payload.get("shortcuts") or []
		if row.get("type") != "DocType"
		or frappe.db.exists("DocType", row.get("link_to"))
	]

	workspace = frappe.get_doc(payload)
	workspace.flags.ignore_links = True
	workspace.insert(ignore_permissions=True)


def _ensure_attendance_request_label():
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	ws = frappe.get_doc("Workspace", name)
	changed = False
	for row in ws.links or []:
		if row.link_to == "Attendance Request" and row.label in (
			"Work From Home",
			"WFH",
			"WFH Request",
		):
			row.label = "Attendance Request"
			changed = True
	for row in ws.shortcuts or []:
		if row.link_to == "Attendance Request" and row.label in (
			"Work From Home",
			"WFH",
			"WFH Request",
		):
			row.label = "Attendance Request"
			changed = True
	if changed:
		ws.flags.ignore_links = True
		ws.flags.ignore_permissions = True
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)


def _ensure_approver_filter_shortcuts():
	"""For Approvers: DocType list shortcuts with stats_filter (no custom pages)."""
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	ws = frappe.get_doc("Workspace", name)
	changed = False

	# Drop obsolete quick lists / page links
	kept_ql = [
		row
		for row in (ws.quick_lists or [])
		if row.label not in LEGACY_PENDING_LABELS
	]
	if len(kept_ql) != len(ws.quick_lists or []):
		ws.set("quick_lists", kept_ql)
		changed = True

	if not any(row.label == "For Approvers" for row in ws.links or []):
		ws.append("links", {"type": "Card Break", "label": "For Approvers", "hidden": 0})
		changed = True

	# Links under For Approvers → DocTypes (filters applied via shortcuts)
	desired_links = [
		(LEAVE_PENDING_LABEL, "Leave Application"),
		(ATTENDANCE_PENDING_LABEL, "Attendance Request"),
	]
	for label, doctype in desired_links:
		found = False
		for row in ws.links or []:
			if row.label in LEGACY_PENDING_LABELS and doctype == "Leave Application":
				row.label = LEAVE_PENDING_LABEL
				row.link_type = "DocType"
				row.link_to = "Leave Application"
				found = True
				changed = True
			elif row.label == label:
				row.link_type = "DocType"
				row.link_to = doctype
				found = True
		if not found and frappe.db.exists("DocType", doctype):
			ws.append(
				"links",
				{
					"type": "Link",
					"label": label,
					"link_type": "DocType",
					"link_to": doctype,
					"hidden": 0,
				},
			)
			changed = True

	# Remove leftover Page link to pending-leave-approval
	kept_links = []
	removed_page_link = False
	for row in ws.links or []:
		if row.link_type == "Page" and row.link_to == "pending-leave-approval":
			removed_page_link = True
			changed = True
			continue
		kept_links.append(row)
	if removed_page_link:
		ws.set("links", kept_links)

	desired_shortcuts = [
		{
			"type": "DocType",
			"label": LEAVE_PENDING_LABEL,
			"link_to": "Leave Application",
			"doc_view": "List",
			"color": "Orange",
			"stats_filter": LEAVE_PENDING_FILTER,
		},
		{
			"type": "DocType",
			"label": ATTENDANCE_PENDING_LABEL,
			"link_to": "Attendance Request",
			"doc_view": "List",
			"color": "Orange",
			"stats_filter": ATTENDANCE_REQUEST_DRAFT_FILTER,
		},
	]

	# Upgrade / add shortcuts
	for spec in desired_shortcuts:
		matched = False
		for row in ws.shortcuts or []:
			if row.label in LEGACY_PENDING_LABELS and spec["link_to"] == "Leave Application":
				_apply_shortcut_spec(row, spec)
				matched = True
				changed = True
				break
			if row.label == spec["label"]:
				_apply_shortcut_spec(row, spec)
				matched = True
				changed = True
				break
		if not matched and frappe.db.exists("DocType", spec["link_to"]):
			ws.append("shortcuts", spec)
			changed = True

	# Drop Page shortcut to custom leave page
	kept_sc = []
	for row in ws.shortcuts or []:
		if row.type == "Page" and row.link_to == "pending-leave-approval":
			changed = True
			continue
		kept_sc.append(row)
	ws.set("shortcuts", kept_sc)

	# Content blocks: For Approvers card + two filtered shortcuts
	try:
		blocks = json.loads(ws.content or "[]") if isinstance(ws.content, str) else list(ws.content or [])
	except Exception:
		blocks = []

	intro = (
		"Self-service for daily work, attendance, and leave. "
		"For Approvers shortcuts open standard lists filtered to your queue."
	)
	for block in blocks:
		if isinstance(block, dict) and block.get("id") == "eh-intro":
			data = block.setdefault("data", {})
			if data.get("text") != intro:
				data["text"] = intro
				changed = True

	# Remove quick_list / old pending-leave page shortcut blocks
	new_blocks = []
	for b in blocks:
		if not isinstance(b, dict):
			new_blocks.append(b)
			continue
		btype = b.get("type")
		data = b.get("data") or {}
		if btype == "quick_list" and data.get("quick_list_name") in LEGACY_PENDING_LABELS:
			changed = True
			continue
		if btype == "shortcut" and data.get("shortcut_name") in (
			"Pending Leave Approval",
			*LEGACY_PENDING_LABELS,
		):
			# replace below
			changed = True
			continue
		new_blocks.append(b)

	if not any(
		isinstance(b, dict)
		and b.get("type") == "card"
		and (b.get("data") or {}).get("card_name") == "For Approvers"
		for b in new_blocks
	):
		new_blocks.append(
			{"id": "eh-card-appr", "type": "card", "data": {"card_name": "For Approvers", "col": 4}}
		)
		changed = True

	for sid, label in (
		("eh-short-leave", LEAVE_PENDING_LABEL),
		("eh-short-ar", ATTENDANCE_PENDING_LABEL),
	):
		if not any(
			isinstance(b, dict)
			and b.get("type") == "shortcut"
			and (b.get("data") or {}).get("shortcut_name") == label
			for b in new_blocks
		):
			new_blocks.append(
				{"id": sid, "type": "shortcut", "data": {"shortcut_name": label, "col": 4}}
			)
			changed = True

	ws.content = json.dumps(new_blocks)

	if "Leave Approver" not in {r.role for r in ws.roles or []}:
		ws.append("roles", {"role": "Leave Approver"})
		changed = True

	if changed:
		ws.flags.ignore_links = True
		ws.flags.ignore_permissions = True
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)


def _apply_shortcut_spec(row, spec):
	row.type = spec["type"]
	row.label = spec["label"]
	row.link_to = spec["link_to"]
	row.doc_view = spec.get("doc_view") or "List"
	row.color = spec.get("color") or "Orange"
	row.stats_filter = spec.get("stats_filter")


def _ensure_sidebar():
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		_ensure_sidebar_home_link()
		_ensure_sidebar_approver_links()
		return

	items = [
		{
			"type": "Link",
			"label": WORKSPACE_NAME,
			"link_to": WORKSPACE_NAME,
			"link_type": "Workspace",
			"icon": "briefcase",
			"child": 0,
			"collapsible": 0,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 0,
		},
		{
			"type": "Section Break",
			"label": "Self Service",
			"icon": "users",
			"collapsible": 1,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 1,
			"child": 0,
		},
		_doctype_item("Daily Work Log", "file-text"),
		_doctype_item("Attendance Request", "calendar"),
		_doctype_item("Leave Application", "calendar"),
		_doctype_item("Attendance", "check-circle"),
		_doctype_item("Attendance Regularization Request", "edit"),
		{
			"type": "Section Break",
			"label": "For Approvers",
			"icon": "check-circle",
			"collapsible": 1,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 1,
			"child": 0,
		},
		_doctype_item("Leave Application", "calendar", label=LEAVE_PENDING_LABEL),
		_doctype_item("Attendance Request", "calendar", label=ATTENDANCE_PENDING_LABEL),
	]

	sidebar = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar",
			"title": SIDEBAR_NAME,
			"header_icon": "briefcase",
			"items": items,
		}
	)
	sidebar.insert(ignore_permissions=True)


def _doctype_item(doctype, icon, label=None):
	return {
		"type": "Link",
		"label": label
		or (doctype if doctype != "Attendance Request" else "Attendance Request"),
		"link_to": doctype,
		"link_type": "DocType",
		"icon": icon,
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _ensure_sidebar_home_link():
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	changed = False
	for row in sidebar.items:
		if row.link_type == "Workspace" and row.link_to in LEGACY_WORKSPACE_NAMES:
			row.link_to = WORKSPACE_NAME
			row.label = WORKSPACE_NAME
			changed = True
	if changed:
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)


def _ensure_sidebar_approver_links():
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	changed = False

	# Convert old page pending links to DocType leave filter link
	for row in sidebar.items or []:
		if row.label in LEGACY_PENDING_LABELS or (
			row.link_type == "Page" and row.link_to == "pending-leave-approval"
		):
			row.label = LEAVE_PENDING_LABEL
			row.link_type = "DocType"
			row.link_to = "Leave Application"
			changed = True

	labels = {row.label for row in sidebar.items or []}
	if "For Approvers" not in labels:
		sidebar.append(
			"items",
			{
				"type": "Section Break",
				"label": "For Approvers",
				"icon": "check-circle",
				"collapsible": 1,
				"indent": 0,
				"keep_closed": 0,
				"show_arrow": 1,
				"child": 0,
			},
		)
		changed = True

	if LEAVE_PENDING_LABEL not in labels:
		sidebar.append(
			"items",
			_doctype_item("Leave Application", "calendar", label=LEAVE_PENDING_LABEL),
		)
		changed = True

	if ATTENDANCE_PENDING_LABEL not in labels:
		sidebar.append(
			"items",
			_doctype_item("Attendance Request", "calendar", label=ATTENDANCE_PENDING_LABEL),
		)
		changed = True

	if changed:
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)


def _get_workspace_payload() -> dict:
	workspace_path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "my_work", "my_work.json"
	)
	with open(workspace_path, encoding="utf-8") as handle:
		return json.load(handle)
