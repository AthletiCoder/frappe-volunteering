"""Create-once My Expenses workspace + sidebar; strip accounting links from Volunteering."""

from __future__ import annotations

import json

import frappe

from volunteering.volunteering.accounting_dashboard.setup import (
	ACCOUNTS_OPS_SIDEBAR_SECTION,
	BUDGET_PAGE_SPECS,
	BUDGET_SIDEBAR_SECTION,
	PENDING_SIDEBAR_SECTION,
	RETIRED_PENDING_PAGES,
	_accounts_ops_sidebar_block,
	_approvals_sidebar_block,
	_budget_sidebar_block,
	_is_valid_sidebar_link,
)

WORKSPACE_NAME = "My Expenses"
SIDEBAR_NAME = "My Expenses"
LEGACY_WORKSPACE_NAMES = ("Accounts",)
LEGACY_SIDEBAR_NAMES = ("Accounts",)

PENDING_APPROVER_FILTER = '[["{doctype}","pending_approver","=",frappe.session.user]]'
REIMBURSE_FILTER = (
	'[["Expense Claim","docstatus","=",1],'
	'["Expense Claim","approval_status","=","Approved"],'
	'["Expense Claim","status","=","Unpaid"]]'
)
VENDOR_PAY_FILTER = (
	'[["Purchase Invoice","docstatus","=",1],'
	'["Purchase Invoice","outstanding_amount",">",0]]'
)


def ensure_accounts_workspace():
	"""Backwards-compatible entry point."""
	ensure_my_expenses()


def ensure_my_expenses():
	try:
		_rename_legacy_workspace()
		_rename_legacy_sidebar()
		_ensure_workspace_once()
		_ensure_staff_spend_links()
		_ensure_approval_and_ops_shortcuts()
		_ensure_sidebar()
		_strip_accounting_from_volunteering_sidebar()
	except Exception:
		frappe.log_error(title="My Expenses setup failed", message=frappe.get_traceback())


def _ensure_staff_spend_links():
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	ws = frappe.get_doc("Workspace", name)
	existing = {(row.link_type, row.link_to) for row in ws.links if row.link_to}
	changed = False

	if ("DocType", "Purchase Invoice") not in existing and frappe.db.exists(
		"DocType", "Purchase Invoice"
	):
		ws.append(
			"links",
			{
				"type": "Link",
				"label": "Purchase Invoice",
				"link_to": "Purchase Invoice",
				"link_type": "DocType",
			},
		)
		changed = True

	if ("Report", "Employee Advances with Residual") not in existing and frappe.db.exists(
		"Report", "Employee Advances with Residual"
	):
		ws.append(
			"links",
			{
				"type": "Link",
				"label": "Advances with Residual",
				"link_to": "Employee Advances with Residual",
				"link_type": "Report",
			},
		)
		changed = True

	shortcut_keys = {(s.type, s.link_to, s.label) for s in ws.shortcuts or []}
	if ("DocType", "Employee Advance", "Employee Advance") not in shortcut_keys and frappe.db.exists(
		"DocType", "Employee Advance"
	):
		ws.append(
			"shortcuts",
			{
				"type": "DocType",
				"link_to": "Employee Advance",
				"label": "Employee Advance",
				"doc_view": "List",
				"color": "Blue",
			},
		)
		changed = True

	if changed:
		ws.flags.ignore_links = True
		ws.flags.ignore_permissions = True
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)


def _ensure_approval_and_ops_shortcuts():
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	ws = frappe.get_doc("Workspace", name)
	changed = False

	approval_specs = [
		("Expense Claims Pending Me", "Expense Claim", PENDING_APPROVER_FILTER.format(doctype="Expense Claim")),
		("Advances Pending Me", "Employee Advance", PENDING_APPROVER_FILTER.format(doctype="Employee Advance")),
		("Purchase Orders Pending Me", "Purchase Order", PENDING_APPROVER_FILTER.format(doctype="Purchase Order")),
	]
	ops_specs = [
		("Claims to Reimburse", "Expense Claim", REIMBURSE_FILTER),
		("Vendor Invoices to Pay", "Purchase Invoice", VENDOR_PAY_FILTER),
	]
	queue_specs = [
		(label, doctype, stats_filter)
		for label, doctype, stats_filter in approval_specs + ops_specs
		if frappe.db.exists("DocType", doctype)
		and not (
			"pending_approver" in stats_filter
			and not frappe.db.has_column(doctype, "pending_approver")
		)
	]

	# Rebuild card links in canonical order (filters live on shortcuts)
	desired_links = _canonical_workspace_links(queue_specs)
	current_links = [
		(row.type, row.label, row.link_type, row.link_to)
		for row in ws.links or []
	]
	desired_keys = [
		(row["type"], row["label"], row.get("link_type"), row.get("link_to"))
		for row in desired_links
	]
	if current_links != desired_keys:
		ws.set("links", [])
		for row in desired_links:
			ws.append("links", row)
		changed = True

	for label, doctype, stats_filter in queue_specs:
		matched = False
		for row in ws.shortcuts or []:
			if row.label == label:
				if (
					row.type != "DocType"
					or row.link_to != doctype
					or row.stats_filter != stats_filter
					or row.doc_view != "List"
				):
					row.type = "DocType"
					row.link_to = doctype
					row.doc_view = "List"
					row.color = "Orange"
					row.stats_filter = stats_filter
					changed = True
				matched = True
				break
		if not matched:
			ws.append(
				"shortcuts",
				{
					"type": "DocType",
					"label": label,
					"link_to": doctype,
					"doc_view": "List",
					"color": "Orange",
					"stats_filter": stats_filter,
				},
			)
			changed = True

	# Drop shortcuts that still point at retired pages
	kept_shortcuts = []
	for row in ws.shortcuts or []:
		if row.type == "Page" and row.link_to in RETIRED_PENDING_PAGES:
			changed = True
			continue
		kept_shortcuts.append(row)
	if len(kept_shortcuts) != len(ws.shortcuts or []):
		ws.set("shortcuts", [])
		for row in kept_shortcuts:
			ws.append("shortcuts", row.as_dict() if hasattr(row, "as_dict") else row)

	try:
		blocks = json.loads(ws.content or "[]") if isinstance(ws.content, str) else list(ws.content or [])
	except Exception:
		blocks = []
	existing_sc = {
		(b.get("data") or {}).get("shortcut_name")
		for b in blocks
		if isinstance(b, dict) and b.get("type") == "shortcut"
	}
	for i, (label, _dt, _f) in enumerate(queue_specs):
		if label not in existing_sc and any(s.label == label for s in ws.shortcuts or []):
			blocks.append(
				{
					"id": f"ac-short-queue-{i}",
					"type": "shortcut",
					"data": {"shortcut_name": label, "col": 4},
				}
			)
			changed = True
	ws.content = json.dumps(blocks)

	if changed:
		ws.flags.ignore_links = True
		ws.flags.ignore_permissions = True
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)


def _canonical_workspace_links(queue_specs):
	"""Card Breaks + links in display order for My Expenses."""
	by_label = {label: doctype for label, doctype, _f in queue_specs}

	def _link(label, link_type, link_to, **extra):
		row = {
			"type": "Link",
			"label": label,
			"link_type": link_type,
			"link_to": link_to,
			"hidden": 0,
			"is_query_report": 0,
			"onboard": 0,
		}
		row.update(extra)
		return row

	def _break(label):
		return {
			"type": "Card Break",
			"label": label,
			"hidden": 0,
			"is_query_report": 0,
			"onboard": 0,
			"link_type": "DocType",
		}

	links = [
		_break("My Spend"),
		_link("Expense Claim", "DocType", "Expense Claim"),
		_link("Employee Advance", "DocType", "Employee Advance"),
		_link("Purchase Order", "DocType", "Purchase Order"),
		_break("Approvals"),
	]
	for label in (
		"Expense Claims Pending Me",
		"Advances Pending Me",
		"Purchase Orders Pending Me",
	):
		if label in by_label:
			links.append(_link(label, "DocType", by_label[label]))

	links.append(_break("Accounts Ops"))
	for label in ("Claims to Reimburse", "Vendor Invoices to Pay"):
		if label in by_label:
			links.append(_link(label, "DocType", by_label[label]))

	links.extend(
		[
			_break("Budgets"),
			_link("Budget Health", "Page", "project-budget-health"),
			_link("Project", "DocType", "Project"),
			_link("Purchase Invoice", "DocType", "Purchase Invoice"),
		]
	)
	if frappe.db.exists("Report", "Employee Advances with Residual"):
		links.append(
			_link(
				"Advances with Residual",
				"Report",
				"Employee Advances with Residual",
				report_ref_doctype="Employee Advance",
			)
		)
	return links



def _workspace_exists(name: str = WORKSPACE_NAME) -> bool:
	return bool(
		frappe.db.exists("Workspace", name)
		or frappe.db.get_value("Workspace", {"label": name}, "name")
		or frappe.db.get_value("Workspace", {"title": name}, "name")
	)


def _rename_legacy_workspace():
	if _workspace_exists(WORKSPACE_NAME):
		for legacy in LEGACY_WORKSPACE_NAMES:
			found = (
				frappe.db.exists("Workspace", legacy)
				or frappe.db.get_value("Workspace", {"label": legacy}, "name")
			)
			if found and found != WORKSPACE_NAME:
				frappe.delete_doc("Workspace", found, force=True, ignore_permissions=True)
		return

	for legacy in LEGACY_WORKSPACE_NAMES:
		found = (
			frappe.db.exists("Workspace", legacy)
			or frappe.db.get_value("Workspace", {"label": legacy}, "name")
			or frappe.db.get_value("Workspace", {"title": legacy}, "name")
		)
		if not found:
			continue
		ws = frappe.get_doc("Workspace", found)
		ws.label = WORKSPACE_NAME
		ws.title = WORKSPACE_NAME
		ws.icon = "expense"
		if ws.content and "Accounts" in ws.content:
			ws.content = ws.content.replace(">Accounts<", ">My Expenses<")
			ws.content = ws.content.replace('"Accounts"', '"My Expenses"')
		ws.flags.ignore_links = True
		ws.flags.ignore_permissions = True
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)
		if ws.name != WORKSPACE_NAME:
			frappe.rename_doc("Workspace", ws.name, WORKSPACE_NAME, force=True, merge=False)
		return


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
			if item.label == "Accounts" and item.link_type == "Workspace":
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
			row.get("link_type") == "Page"
			and frappe.db.exists("Page", row.get("link_to"))
			and row.get("link_to") not in RETIRED_PENDING_PAGES
		)
		or (
			row.get("link_type") == "Report"
			and frappe.db.exists("Report", row.get("link_to"))
		)
	]
	payload["shortcuts"] = [
		row
		for row in payload.get("shortcuts") or []
		if (row.get("type") == "DocType" and frappe.db.exists("DocType", row.get("link_to")))
		or (
			row.get("type") == "Page"
			and frappe.db.exists("Page", row.get("link_to"))
			and row.get("link_to") not in RETIRED_PENDING_PAGES
		)
		or row.get("type") not in ("DocType", "Page")
	]

	workspace = frappe.get_doc(payload)
	workspace.flags.ignore_links = True
	workspace.insert(ignore_permissions=True)


def _get_workspace_payload() -> dict:
	path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "my_expenses", "my_expenses.json"
	)
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def _canonical_sidebar_items():
	items = [
		{
			"type": "Link",
			"label": WORKSPACE_NAME,
			"link_to": WORKSPACE_NAME,
			"link_type": "Workspace",
			"icon": "layout-dashboard",
			"child": 0,
			"collapsible": 0,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 0,
		}
	]
	items.extend(_approvals_sidebar_block())
	items.extend(_accounts_ops_sidebar_block())
	items.extend(_budget_sidebar_block())
	items.extend(
		[
			{
				"type": "Section Break",
				"label": "Documents",
				"icon": "file",
				"collapsible": 1,
				"indent": 0,
				"keep_closed": 0,
				"show_arrow": 1,
				"child": 0,
			},
			_doctype_item("Expense Claim", "expense"),
			_doctype_item("Employee Advance", "money-coins-1"),
			_doctype_item("Purchase Order", "buying"),
			_doctype_item("Purchase Invoice", "file"),
			_doctype_item("Project", "project"),
		]
	)
	return items


def _ensure_sidebar():
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		_refresh_sidebar_items()
		return

	sidebar = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar",
			"title": SIDEBAR_NAME,
			"header_icon": "expense",
			"items": _canonical_sidebar_items(),
		}
	)
	sidebar.insert(ignore_permissions=True)


def _doctype_item(doctype, icon):
	return {
		"type": "Link",
		"label": doctype,
		"link_to": doctype,
		"link_type": "DocType",
		"icon": icon,
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _refresh_sidebar_items():
	"""Rebuild My Expenses sidebar to canonical order (approvals / ops / budget / docs)."""
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	canonical = _canonical_sidebar_items()
	current = [
		(row.type, row.label, row.link_type, row.link_to)
		for row in sidebar.items or []
	]
	desired = [
		(row.get("type"), row.get("label"), row.get("link_type"), row.get("link_to"))
		for row in canonical
	]
	if current == desired:
		return

	sidebar.items = []
	for row in canonical:
		sidebar.append("items", row)
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)


def _strip_accounting_from_volunteering_sidebar():
	if not frappe.db.exists("Workspace Sidebar", "Volunteering"):
		return

	budget_pages = {spec["name"] for spec in BUDGET_PAGE_SPECS}
	all_pages = set(RETIRED_PENDING_PAGES) | budget_pages

	sidebar = frappe.get_doc("Workspace Sidebar", "Volunteering")
	filtered = [
		item
		for item in sidebar.items
		if _is_valid_sidebar_link(item)
		and not (item.link_type == "Page" and item.link_to in all_pages)
		and item.label
		not in (PENDING_SIDEBAR_SECTION, ACCOUNTS_OPS_SIDEBAR_SECTION, BUDGET_SIDEBAR_SECTION, "Pending Approvals")
	]
	if len(filtered) == len(sidebar.items):
		return

	sidebar.items = []
	for item in filtered:
		sidebar.append("items", item.as_dict())
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)
