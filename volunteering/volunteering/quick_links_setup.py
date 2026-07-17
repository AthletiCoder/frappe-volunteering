"""Create-once Quick Links workspace — never overwrite Desk customizations."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "Quick Links"
LEGACY_NAMES = ("Staff Hub", "Employee Hub")


def ensure_quick_links():
	"""Insert default Quick Links only if missing; never rewrite content/links.

	Renames legacy Staff Hub / Employee Hub workspaces in place when present.
	"""
	try:
		if _rename_legacy_workspace():
			return

		if _workspace_exists(WORKSPACE_NAME):
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
	except Exception:
		frappe.log_error(title="Quick Links setup failed", message=frappe.get_traceback())


# Backwards-compatible aliases
ensure_staff_hub = ensure_quick_links
ensure_employee_hub = ensure_quick_links


def _find_legacy_workspace() -> str | None:
	for legacy_name in LEGACY_NAMES:
		found = (
			frappe.db.exists("Workspace", legacy_name)
			or frappe.db.get_value("Workspace", {"label": legacy_name}, "name")
			or frappe.db.get_value("Workspace", {"title": legacy_name}, "name")
		)
		if found:
			return found
	return None


def _rename_legacy_workspace() -> bool:
	legacy = _find_legacy_workspace()
	if not legacy:
		return False

	if _workspace_exists(WORKSPACE_NAME):
		if legacy != WORKSPACE_NAME:
			frappe.delete_doc("Workspace", legacy, force=True, ignore_permissions=True)
		return True

	ws = frappe.get_doc("Workspace", legacy)
	ws.label = WORKSPACE_NAME
	ws.title = WORKSPACE_NAME
	ws.icon = "link"
	if ws.content:
		for old in LEGACY_NAMES:
			if old in ws.content:
				ws.content = ws.content.replace(old, WORKSPACE_NAME)
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.flags.ignore_validate = True
	ws.save(ignore_permissions=True)
	if ws.name != WORKSPACE_NAME:
		frappe.rename_doc("Workspace", ws.name, WORKSPACE_NAME, force=True, merge=False)
	return True


def _workspace_exists(name: str) -> bool:
	return bool(
		frappe.db.exists("Workspace", name)
		or frappe.db.get_value("Workspace", {"label": name}, "name")
		or frappe.db.get_value("Workspace", {"title": name}, "name")
	)


def _get_workspace_payload() -> dict:
	workspace_path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "quick_links", "quick_links.json"
	)
	with open(workspace_path, encoding="utf-8") as handle:
		return json.load(handle)
