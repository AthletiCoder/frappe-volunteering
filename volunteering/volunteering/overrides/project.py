import frappe
from erpnext.projects.doctype.project.project import Project

from volunteering.volunteering import project_workspace as workspace


class VolunteeringProject(Project):
	def get_permlevel_access(self, permission_type="write"):
		levels = super().get_permlevel_access(permission_type)
		if permission_type == "read" and workspace.can_view_finance(self) and 2 not in levels:
			levels.append(2)
		return levels


def revision_permission(doc, user=None, ptype=None, **kwargs):
	return ptype in ("read", "select", "print", "report") and workspace.can_view_finance(
		frappe.get_doc("Project", doc.project), user
	)


def revision_query(user=None):
	if workspace._is_admin(user) or workspace.FINANCE_READ_ROLES.intersection(workspace._roles(user)):
		return ""
	escaped = frappe.db.escape(user or frappe.session.user)
	return f"EXISTS (SELECT 1 FROM `tabProject Participant` pm WHERE pm.parent=`tabProject Budget Revision`.project AND pm.parenttype='Project' AND pm.user={escaped} AND pm.access_level='Financial')"
