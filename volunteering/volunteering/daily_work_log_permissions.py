import frappe


HR_ROLES = {"HR Manager", "HR User", "System Manager"}


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return ""

	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	conditions = []

	own_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if own_employee:
		conditions.append(f"`tabDaily Work Log`.employee = {frappe.db.escape(own_employee)}")

	if manager_employee:
		conditions.append(
			f"""`tabDaily Work Log`.employee IN (
				SELECT name FROM `tabEmployee` WHERE reports_to = {frappe.db.escape(manager_employee)}
			)"""
		)

	if conditions:
		return f"({' OR '.join(conditions)})"

	return "1=0"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return True

	if ptype in {"read", "print", "email", "export", "report"}:
		return can_view_work_log(doc, user)

	if ptype in {"write", "create", "submit", "cancel", "delete"}:
		return can_edit_work_log(doc, user)

	return False


def can_view_work_log(doc, user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	if doc.employee == employee:
		return True

	return frappe.db.get_value("Employee", doc.employee, "reports_to") == employee


def can_edit_work_log(doc, user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	if doc.employee != employee:
		return False

	if doc.docstatus == 1 and doc.status == "Reviewed":
		return False

	return True


def can_review_work_log(doc):
	user = frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return True

	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not manager_employee:
		return False

	return frappe.db.get_value("Employee", doc.employee, "reports_to") == manager_employee
