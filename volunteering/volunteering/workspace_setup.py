import frappe


WORKSPACE_NAME = "Volunteering"
SIDEBAR_NAME = "Volunteering"


def ensure_defaults():
	"""Create default workspace UI only on fresh sites — never overwrite prod customizations."""
	ensure_volunteering_workspace()
	ensure_volunteering_sidebar()


def backfill_participation_relationship_managers():
	frappe.db.sql(
		"""
		UPDATE `tabParticipation` p
		JOIN `tabVolunteer` v ON v.name = p.volunteer
		SET p.relationship_manager = v.relationship_manager
		WHERE IFNULL(p.relationship_manager, '') != IFNULL(v.relationship_manager, '')
		"""
	)


def ensure_volunteering_workspace():
	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc(
		{
			"doctype": "Workspace",
			"label": WORKSPACE_NAME,
			"title": WORKSPACE_NAME,
			"module": "Volunteering",
			"app": "volunteering",
			"public": 1,
			"icon": "hand-heart",
			"indicator_color": "green",
			"content": '[{"id":"header","type":"header","data":{"text":"<span class=\\"h4\\">Volunteering Workspace</span>","col":12}}]',
			"quick_lists": [
				{
					"document_type": "NGO Event",
					"label": "Recent Events",
					"quick_list_filter": "[]",
				}
			],
		}
	)
	workspace.insert(ignore_permissions=True)


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
