"""Keep pre-workspace test records out of Home without altering Desk history.

The governed Project setup marker distinguishes newly approved Home projects
from the existing legacy projects. Home financial records must belong to one of
those governed projects; records with no project remain Desk-only history.
"""

import frappe
from frappe import _
from frappe.utils import cint


def home_project_names():
	return frappe.get_all(
		"Project",
		filters={"project_setup_version": [">", 0]},
		pluck="name",
		limit_page_length=0,
	)


def home_project_filter(field="project"):
	"""Query only Home projects, before list limits and pagination apply."""
	return {field: ["in", home_project_names() or [""]]}


def is_home_project(project):
	return bool(project and cint(frappe.db.get_value("Project", project, "project_setup_version")) > 0)


def require_home_project(project):
	if not is_home_project(project):
		frappe.throw(_("This record is not available in Home."), frappe.PermissionError)


def is_home_advance(advance):
	return is_home_project(advance.get("intended_project"))


def require_home_advance(advance):
	if not is_home_advance(advance):
		frappe.throw(_("This record is not available in Home."), frappe.PermissionError)
