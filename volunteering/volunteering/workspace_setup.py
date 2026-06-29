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
