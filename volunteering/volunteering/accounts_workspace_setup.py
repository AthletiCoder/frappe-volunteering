"""Create / rebuild My Expenses workspace + slim sidebar."""

from __future__ import annotations

import json

import frappe

from volunteering.volunteering.accounting_dashboard.setup import (
	RETIRED_PENDING_PAGES,
	SPA_ADVANCE_PORTAL,
	SPA_BUDGET_HEALTH,
	_is_valid_sidebar_link,
)
WORKSPACE_NAME = "My Expenses"
SIDEBAR_NAME = "My Expenses"
LEGACY_WORKSPACE_NAMES = ("Accounts",)
LEGACY_SIDEBAR_NAMES = ("Accounts",)

PENDING_APPROVER_FILTER = '[["{doctype}","pending_approver","=",frappe.session.user]]'
MY_DRAFT_EC = (
	'[["Expense Claim","docstatus","=",0],'
	'["Expense Claim","workflow_state","in",["Draft","Rejected"]]]'
)
MY_DRAFT_EA = (
	'[["Employee Advance","docstatus","=",0],'
	'["Employee Advance","workflow_state","in",["Draft","Rejected"]]]'
)
MY_DRAFT_PO = (
	'[["Purchase Order","docstatus","=",0],'
	'["Purchase Order","workflow_state","in",["Draft","Rejected"]]]'
)
REIMBURSE_FILTER = (
	'[["Expense Claim","docstatus","=",1],'
	'["Expense Claim","approval_status","=","Approved"],'
	'["Expense Claim","status","=","Unpaid"]]'
)
VENDOR_PAY_FILTER = (
	'[["Purchase Invoice","docstatus","=",1],'
	'["Purchase Invoice","outstanding_amount",">",0]]'
)

MY_SPEND_SHORTCUTS = (
	{
		"label": "My Expense Claims",
		"link_to": "Expense Claim",
		"color": "Blue",
		"stats_filter": MY_DRAFT_EC,
	},
	{
		"label": "My Advances",
		"link_to": "Employee Advance",
		"color": "Blue",
		"stats_filter": MY_DRAFT_EA,
	},
	{
		"label": "My Purchase Orders",
		"link_to": "Purchase Order",
		"color": "Blue",
		"stats_filter": MY_DRAFT_PO,
	},
	{
		"label": "Advance Portal",
		"link_to": SPA_ADVANCE_PORTAL["url"],
		"type": "URL",
		"color": "Blue",
		"stats_filter": "",
	},
)

APPROVAL_SHORTCUTS = (
	{
		"label": "Expense Claims Pending Me",
		"link_to": "Expense Claim",
		"color": "Orange",
		"stats_filter": PENDING_APPROVER_FILTER.format(doctype="Expense Claim"),
	},
	{
		"label": "Advances Pending Me",
		"link_to": "Employee Advance",
		"color": "Orange",
		"stats_filter": PENDING_APPROVER_FILTER.format(doctype="Employee Advance"),
	},
	{
		"label": "Purchase Orders Pending Me",
		"link_to": "Purchase Order",
		"color": "Orange",
		"stats_filter": PENDING_APPROVER_FILTER.format(doctype="Purchase Order"),
	},
)

OPS_SHORTCUTS = (
	{
		"label": "Claims to Reimburse",
		"link_to": "Expense Claim",
		"color": "Orange",
		"stats_filter": REIMBURSE_FILTER,
	},
	{
		"label": "Vendor Invoices to Pay",
		"link_to": "Purchase Invoice",
		"color": "Orange",
		"stats_filter": VENDOR_PAY_FILTER,
	},
	{
		"label": "Approval & Advance Limits",
		"link_to": "Approval and Advance Limits",
		"color": "Grey",
		"stats_filter": "",
	},
)


def ensure_accounts_workspace():
	ensure_my_expenses()


def ensure_my_expenses():
	try:
		_rename_legacy_workspace()
		_ensure_workspace_once()
		_rebuild_workspace()
		_ensure_minimal_sidebar()
		_strip_accounting_from_volunteering_sidebar()
	except Exception:
		frappe.log_error(title="My Expenses setup failed", message=frappe.get_traceback())


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
	name = (
		frappe.db.exists("Workspace", WORKSPACE_NAME)
		or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
	)
	if not name:
		return

	ws = frappe.get_doc("Workspace", name)
	ws.set("shortcuts", [])
	ws.set("links", [])
	ws.set("roles", [])

	sections = (
		("My Spend", MY_SPEND_SHORTCUTS),
		("Awaiting my Approval", APPROVAL_SHORTCUTS),
		("Accounts Ops", OPS_SHORTCUTS),
	)

	for section_label, specs in sections:
		ws.append("links", {"type": "Card Break", "label": section_label, "hidden": 0})
		for spec in specs:
			stype = spec.get("type") or "DocType"
			if stype == "DocType" and not frappe.db.exists("DocType", spec["link_to"]):
				continue
			if stype == "Page" and not frappe.db.exists("Page", spec["link_to"]):
				continue
			if stype == "DocType" and "pending_approver" in (spec.get("stats_filter") or ""):
				if not frappe.db.has_column(spec["link_to"], "pending_approver"):
					continue

			# Workspace Link only supports DocType / Page / Report — SPA routes are shortcuts only
			if stype != "URL":
				link_type = "Page" if stype == "Page" else "DocType"
				ws.append(
					"links",
					{
						"type": "Link",
						"label": spec["label"],
						"link_type": link_type,
						"link_to": spec["link_to"],
						"hidden": 0,
					},
				)

			sc = {
				"type": stype if stype in ("DocType", "Page", "URL") else "DocType",
				"label": spec["label"],
				"doc_view": "List",
				"color": spec.get("color") or "Blue",
			}
			if stype == "URL":
				sc["url"] = spec["link_to"]
			else:
				sc["link_to"] = spec["link_to"]
				if spec.get("stats_filter"):
					sc["stats_filter"] = spec.get("stats_filter")
			ws.append("shortcuts", sc)

	ws.append("links", {"type": "Card Break", "label": "Budgets", "hidden": 0})
	# Residual report stays as a Workspace Link; SPA Budget Health is shortcut-only
	if frappe.db.exists("Report", "Employee Advances with Residual"):
		ws.append(
			"links",
			{
				"type": "Link",
				"label": "Advances with Residual",
				"link_type": "Report",
				"link_to": "Employee Advances with Residual",
				"is_query_report": 1,
				"hidden": 0,
				"report_ref_doctype": "Employee Advance",
			},
		)
	ws.append(
		"shortcuts",
		{
			"type": "URL",
			"label": SPA_BUDGET_HEALTH["label"],
			"url": SPA_BUDGET_HEALTH["url"],
			"color": "Green",
		},
	)
	if frappe.db.exists("Report", "Employee Advances with Residual"):
		ws.append(
			"shortcuts",
			{
				"type": "Report",
				"label": "Advances with Residual",
				"link_to": "Employee Advances with Residual",
				"color": "Orange",
				"report_ref_doctype": "Employee Advance",
			},
		)

	for role in (
		"Employee",
		"Accounts User",
		"Accounts Manager",
		"NGO Coordinator",
		"System Manager",
		"Leave Approver",
	):
		if frappe.db.exists("Role", role):
			ws.append("roles", {"role": role})

	content = [
		{
			"id": "ac-header",
			"type": "header",
			"data": {"text": '<span class="h4">My Expenses</span>', "col": 12},
		},
		{
			"id": "ac-intro",
			"type": "paragraph",
			"data": {
				"text": (
					"Your spend requests, approvals awaiting you, and accounts ops queues. "
					"Orange cards show live pending counts — click to open the filtered list."
				),
				"col": 12,
			},
		},
		{"id": "ac-spacer", "type": "spacer", "data": {"col": 12}},
		{"id": "ac-card-spend", "type": "card", "data": {"card_name": "My Spend", "col": 4}},
		{
			"id": "ac-card-appr",
			"type": "card",
			"data": {"card_name": "Awaiting my Approval", "col": 4},
		},
		{"id": "ac-card-ops", "type": "card", "data": {"card_name": "Accounts Ops", "col": 4}},
		{"id": "ac-card-bud", "type": "card", "data": {"card_name": "Budgets", "col": 4}},
	]
	idx = 0
	for _section, specs in sections:
		for spec in specs:
			content.append(
				{
					"id": f"ac-sc-{idx}",
					"type": "shortcut",
					"data": {"shortcut_name": spec["label"], "col": 4},
				}
			)
			idx += 1
	content.append(
		{
			"id": "ac-sc-budget",
			"type": "shortcut",
			"data": {"shortcut_name": "Budget Health", "col": 4},
		}
	)
	if frappe.db.exists("Report", "Employee Advances with Residual"):
		content.append(
			{
				"id": "ac-sc-residual",
				"type": "shortcut",
				"data": {"shortcut_name": "Advances with Residual", "col": 4},
			}
		)
	ws.content = json.dumps(content)

	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.flags.ignore_validate = True
	ws.save(ignore_permissions=True)


def _ensure_minimal_sidebar():
	"""Keep a sidebar shell so Desktop Icons still open the workspace page.
	Do not list spend/approval DocTypes here — those live on workspace shortcuts."""
	_home = {
		"type": "Link",
		"label": WORKSPACE_NAME,
		"link_to": WORKSPACE_NAME,
		"link_type": "Workspace",
		"icon": "expense",
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}
	for legacy in LEGACY_SIDEBAR_NAMES:
		if legacy != SIDEBAR_NAME and frappe.db.exists("Workspace Sidebar", legacy):
			frappe.delete_doc("Workspace Sidebar", legacy, force=True, ignore_permissions=True)

	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
		sidebar.items = []
		sidebar.append("items", _home)
		sidebar.header_icon = "expense"
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)
		return

	frappe.get_doc(
		{
			"doctype": "Workspace Sidebar",
			"title": SIDEBAR_NAME,
			"header_icon": "expense",
			"items": [_home],
		}
	).insert(ignore_permissions=True)


def _section(label, icon):
	return {
		"type": "Section Break",
		"label": label,
		"icon": icon,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 1,
		"child": 0,
	}


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


def _strip_accounting_from_volunteering_sidebar():
	if not frappe.db.exists("Workspace Sidebar", "Volunteering"):
		return

	retired_pages = set(RETIRED_PENDING_PAGES)
	spa_urls = {SPA_ADVANCE_PORTAL["url"], SPA_BUDGET_HEALTH["url"]}

	sidebar = frappe.get_doc("Workspace Sidebar", "Volunteering")
	filtered = [
		item
		for item in sidebar.items
		if _is_valid_sidebar_link(item)
		and not (item.link_type == "Page" and item.link_to in retired_pages)
		and not (
			item.link_type == "URL"
			and (item.get("url") or item.get("link_to")) in spa_urls
		)
		and item.label
		not in (
			"Pending Approvals",
			"Approvals",
			"Accounts Ops",
			"Budgets",
			"Awaiting my Approval",
			"My Spend",
			"Advance Portal",
			"Budget Health",
		)
	]
	if len(filtered) == len(sidebar.items):
		return

	sidebar.items = []
	for item in filtered:
		sidebar.append("items", item.as_dict())
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)


def _get_workspace_payload() -> dict:
	path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "my_expenses", "my_expenses.json"
	)
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)
