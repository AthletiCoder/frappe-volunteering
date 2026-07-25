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
			"items": [
				_link("Volunteering", "Volunteering", "Workspace", "layout-dashboard"),
				_link("Participation", "Participation", "DocType", "handshake"),
				_link("Volunteers", "Volunteer", "DocType", "contact"),
				_link("Events", "NGO Event", "DocType", "hand-heart"),
				_link("Reciprocation", "Reciprocation", "DocType", "handbag"),
				_link("Daily Work Log", "Daily Work Log", "DocType", "clipboard-list"),
			],
		}
	)
	sidebar.insert(ignore_permissions=True)


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
