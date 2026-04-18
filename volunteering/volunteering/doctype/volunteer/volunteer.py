import frappe
from frappe.model.document import Document

class Volunteer(Document):
	def get_permission_query_conditions(user):
		if not user: user = frappe.session.user
		
		# Admins and Coordinators see everything
		if "NGO Admin" in frappe.get_roles(user) or "NGO Coordinator" in frappe.get_roles(user):
			return ""
		
		# Members only see the Volunteer record linked to their User ID
		if "NGO Member" in frappe.get_roles(user):
			return f"`tabVolunteer`.user_id = {frappe.db.escape(user)}"
		
		return "1=0" # Default deny for anyone else

	def has_permission(doc, ptype, user):
		if "NGO Admin" in frappe.get_roles(user) or "NGO Coordinator" in frappe.get_roles(user):
			return True
			
		if "NGO Member" in frappe.get_roles(user):
			# Allow reading and writing only if it's their own record
			if doc.user_id == user:
				# You can further restrict 'ptype' here (e.g., prevent them from deleting)
				if ptype == "delete":
					return False
				return True
				
		return False