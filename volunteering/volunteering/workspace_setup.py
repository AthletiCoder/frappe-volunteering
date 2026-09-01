import json

import frappe


WORKSPACE_NAME = "Volunteering"
SIDEBAR_NAME = "Volunteering"
DASHBOARD_MARKER = "volunteering-dashboard-v2"
EVENT_FILTER_EXPRESSION = "frappe.boot.volunteering_latest_event"
VOLUNTEERING_EVENT_DYNAMIC_FILTER = (
	'[["Participation","event","=",' f'"{EVENT_FILTER_EXPRESSION}"' "]]"
)
VOLUNTEERING_DASHBOARD_WIDGETS = (
	"Total Registrations",
	"Total Kits Requested",
	"Consignments Shipped",
	"Registration Timeline",
	"Volunteer Referral Leaderboard",
	"Kits Distribution",
)


def ensure_defaults():
	"""Create default workspace UI only on fresh sites — never overwrite prod customizations."""
	ensure_volunteering_workspace()
	ensure_volunteering_sidebar()
	sync_volunteering_workspace_dashboard()
	sync_volunteering_dashboard_filters()
	ensure_donation_workspace_widgets()
	ensure_donation_sidebar_link()
	ensure_spa_workspace_shortcuts()
	ensure_spa_sidebar_links()
	ensure_volunteering_core_sidebar_links()


def backfill_participation_relationship_managers():
	frappe.db.sql(
		"""
		UPDATE `tabParticipation` p
		JOIN `tabVolunteer` v ON v.name = p.volunteer
		SET p.relationship_manager = v.relationship_manager
		WHERE IFNULL(p.relationship_manager, '') != IFNULL(v.relationship_manager, '')
		"""
	)


def get_latest_ngo_event():
	return frappe.db.get_value("NGO Event", {}, "name", order_by="creation desc")


def boot_session(bootinfo):
	bootinfo.volunteering_latest_event = get_latest_ngo_event()
	# Used by My Work shortcut filters (self vs approver queues).
	if frappe.session.user and frappe.session.user not in ("Guest", "Administrator"):
		bootinfo.employee = frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user}, "name"
		)
	else:
		bootinfo.employee = None


def ensure_volunteering_workspace():
	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc(_get_workspace_payload())
	workspace.insert(ignore_permissions=True)


def sync_volunteering_workspace_dashboard():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	if _has_dashboard_layout(workspace):
		return

	payload = _get_workspace_payload()
	workspace.content = payload["content"]
	workspace.charts = []
	for row in payload.get("charts", []):
		workspace.append("charts", row)

	workspace.number_cards = []
	for row in payload.get("number_cards", []):
		workspace.append("number_cards", row)

	workspace.shortcuts = []
	for row in payload.get("shortcuts", []):
		workspace.append("shortcuts", row)

	workspace.flags.ignore_links = True
	workspace.save(ignore_permissions=True)


def sync_volunteering_dashboard_filters():
	"""Fix dashboard widgets that still point at removed Volunteering Settings."""
	for widget_name in VOLUNTEERING_DASHBOARD_WIDGETS:
		doctype = "Number Card" if widget_name in {
			"Total Registrations",
			"Total Kits Requested",
			"Consignments Shipped",
		} else "Dashboard Chart"

		if not frappe.db.exists(doctype, widget_name):
			continue

		current_filter = frappe.db.get_value(doctype, widget_name, "dynamic_filters_json") or ""
		if current_filter == VOLUNTEERING_EVENT_DYNAMIC_FILTER:
			continue

		if "Volunteering Settings" not in current_filter and current_filter not in ("", "[]"):
			continue

		frappe.db.set_value(
			doctype,
			widget_name,
			"dynamic_filters_json",
			VOLUNTEERING_EVENT_DYNAMIC_FILTER,
			update_modified=False,
		)


def _has_dashboard_layout(workspace):
	content = workspace.content or ""
	return DASHBOARD_MARKER in content


def _get_workspace_payload():
	workspace_path = frappe.get_app_path(
		"volunteering", "volunteering", "workspace", "volunteering", "volunteering.json"
	)
	with open(workspace_path, encoding="utf-8") as handle:
		return json.load(handle)


def ensure_volunteering_sidebar():
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	sidebar = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar",
			"title": SIDEBAR_NAME,
			"module": "Volunteering",
			"app": "volunteering",
			"header_icon": "earth",
			"standard": 0,
			"items": _core_sidebar_items(),
		}
	)
	sidebar.insert(ignore_permissions=True)


def _core_sidebar_items():
	return [
		_link("Volunteering", "Volunteering", "Workspace", "layout-dashboard"),
		_link("Participation", "Participation", "DocType", "handshake"),
		_link("Volunteers", "Volunteer", "DocType", "contact"),
		_link("Events", "NGO Event", "DocType", "hand-heart"),
		_link("Reciprocation", "Reciprocation", "DocType", "handbag"),
		_link("Daily Work Log", "Daily Work Log", "DocType", "clipboard-list"),
	]


def ensure_volunteering_core_sidebar_links():
	"""Re-add missing desk DocType links after SPA/accounts sidebar churn."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	existing_keys = {_sidebar_item_key(item.as_dict()) for item in sidebar.items}
	added = False
	for row in _core_sidebar_items():
		if _sidebar_item_key(row) in existing_keys:
			continue
		sidebar.append("items", row)
		added = True
	if not added:
		return
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)


def _link(label, link_to, link_type, icon):
	return {
		"type": "Link",
		"label": label,
		"link_to": link_to,
		"link_type": link_type,
		"icon": icon,
		"child": 0,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}


DONATION_NUMBER_CARDS = (
	"Today's Donations",
	"Today's Donation Count",
	"MTD Donations",
)
DONATION_CHART = "Daily Donation Amount"
DONATION_MARKER = "volunteering-donations-v1"


def ensure_donation_workspace_widgets():
	"""Append donation cards/chart to Volunteering workspace once."""
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	content = workspace.content or ""
	if DONATION_MARKER in content:
		return

	# Ensure child table rows exist
	existing_cards = {row.number_card_name for row in workspace.number_cards}
	for card in DONATION_NUMBER_CARDS:
		if card not in existing_cards and frappe.db.exists("Number Card", card):
			workspace.append(
				"number_cards",
				{"label": card, "number_card_name": card},
			)

	existing_charts = {row.chart_name for row in workspace.charts}
	if DONATION_CHART not in existing_charts and frappe.db.exists("Dashboard Chart", DONATION_CHART):
		workspace.append("charts", {"chart_name": DONATION_CHART, "label": DONATION_CHART})

	try:
		blocks = json.loads(content) if content else []
	except json.JSONDecodeError:
		blocks = []

	blocks.append(
		{
			"id": DONATION_MARKER,
			"type": "header",
			"data": {"text": '<span class="h4">Donations</span>', "col": 12},
		}
	)
	blocks.append(
		{
			"id": "vw-card-don-today",
			"type": "number_card",
			"data": {"number_card_name": "Today's Donations", "col": 4},
		}
	)
	blocks.append(
		{
			"id": "vw-card-don-count",
			"type": "number_card",
			"data": {"number_card_name": "Today's Donation Count", "col": 4},
		}
	)
	blocks.append(
		{
			"id": "vw-card-don-mtd",
			"type": "number_card",
			"data": {"number_card_name": "MTD Donations", "col": 4},
		}
	)
	blocks.append(
		{
			"id": "vw-chart-donations",
			"type": "chart",
			"data": {"chart_name": "Daily Donation Amount", "col": 12},
		}
	)
	workspace.content = json.dumps(blocks)
	workspace.flags.ignore_links = True
	workspace.save(ignore_permissions=True)


SPA_LINKS_MARKER = "vw-spa-links-v1"


def ensure_spa_workspace_shortcuts():
	"""Keep campaign dashboard; add URL shortcuts to the Vue SPA pages."""
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	from volunteering.volunteering.home_service import spa_workspace_shortcuts

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	wanted = {row["label"]: row for row in spa_workspace_shortcuts()}
	existing = {row.label: row for row in workspace.shortcuts}
	changed = False
	for label, spec in wanted.items():
		row = existing.get(label)
		if row:
			if row.type != "URL" or (row.url or "") != spec["url"]:
				row.type = "URL"
				row.url = spec["url"]
				row.link_to = ""
				row.color = spec.get("color") or row.color
				changed = True
			continue
		workspace.append("shortcuts", spec)
		changed = True

	content = workspace.content or ""
	if SPA_LINKS_MARKER not in content:
		try:
			blocks = json.loads(content) if content else []
		except json.JSONDecodeError:
			blocks = []
		workspace.content = json.dumps(_spa_shortcut_blocks() + blocks)
		changed = True

	if not changed:
		return
	workspace.flags.ignore_links = True
	workspace.flags.ignore_permissions = True
	workspace.save(ignore_permissions=True)


def _spa_shortcut_blocks():
	return [
		{
			"id": SPA_LINKS_MARKER,
			"type": "header",
			"data": {"text": '<span class="h4">Staff apps</span>', "col": 12},
		},
		{"id": "vw-spa-home", "type": "shortcut", "data": {"shortcut_name": "Home", "col": 3}},
		{"id": "vw-spa-todo", "type": "shortcut", "data": {"shortcut_name": "To-do", "col": 3}},
		{
			"id": "vw-spa-advances",
			"type": "shortcut",
			"data": {"shortcut_name": "Advance Portal", "col": 3},
		},
		{
			"id": "vw-spa-budget",
			"type": "shortcut",
			"data": {"shortcut_name": "Budget Health", "col": 3},
		},
	]


def _url_sidebar_item(label, url, icon):
	return {
		"type": "Link",
		"label": label,
		"link_type": "URL",
		"url": url,
		"icon": icon,
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _section_break(label, icon="home"):
	return {
		"type": "Section Break",
		"label": label,
		"icon": icon,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
		"child": 0,
	}


def _sidebar_item_key(item):
	"""Identity for dedupe — ignore duplicate Staff apps / SPA URL rows."""
	if isinstance(item, dict):
		label = item.get("label") or ""
		item_type = item.get("type") or ""
		link_type = item.get("link_type") or ""
		link_to = item.get("link_to") or ""
		url = item.get("url") or ""
	else:
		label = item.label or ""
		item_type = item.type or ""
		link_type = item.link_type or ""
		link_to = item.link_to or ""
		url = item.url or ""
	if item_type == "Section Break":
		return ("section", label)
	if link_type == "URL":
		return ("url", label, url)
	return ("link", label, link_type, link_to)


SPA_SIDEBAR_LABELS = frozenset({"Staff apps", "Home", "To-do"})


def _strip_spa_url_sidebar_items(sidebar) -> list[dict]:
	"""Remove Home / To-do URL rows — those live on Desktop Icons."""
	from volunteering.volunteering.home_service import HOME_URL, TODOS_URL

	spa_urls = {HOME_URL, TODOS_URL}
	rest: list[dict] = []
	seen: set = set()
	for item in sidebar.items:
		row = item.as_dict()
		label = row.get("label") or ""
		if label in SPA_SIDEBAR_LABELS:
			continue
		if row.get("type") == "Section Break" and label == "Staff apps":
			continue
		if row.get("link_type") == "URL" and (
			(row.get("url") or "") in spa_urls or label in {"Home", "To-do"}
		):
			continue
		key = _sidebar_item_key(row)
		if key in seen:
			continue
		seen.add(key)
		for meta in ("name", "parent", "parenttype", "parentfield", "idx"):
			row.pop(meta, None)
		rest.append(row)
	return rest


def ensure_spa_sidebar_links():
	"""Strip duplicate Home / To-do from the Volunteering workspace sidebar.

	Those SPA pages are linked from Desktop Icons (``ensure_desk_icons`` on migrate).
	Keeping them in the workspace sidebar as well doubled Home and To-do in Desk.
	"""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	rest = _strip_spa_url_sidebar_items(sidebar)
	current_keys = [_sidebar_item_key(item.as_dict()) for item in sidebar.items]
	desired_keys = [_sidebar_item_key(row) for row in rest]
	if current_keys == desired_keys:
		return

	sidebar.set("items", [])
	for row in rest:
		sidebar.append("items", row)
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)


def ensure_donation_sidebar_link():
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	labels = {row.label for row in sidebar.items}
	if "Donations" in labels:
		return

	sidebar.append(
		"items",
		_link("Donations", "Donation", "DocType", "money-coins-1"),
	)
	sidebar.flags.ignore_links = True
	sidebar.save(ignore_permissions=True)
