import frappe


HR_ROLES = {"HR Manager", "HR User", "System Manager"}
MAX_HIERARCHY_DEPTH = 20


def get_reportee_chain(manager_employee):
	"""All employees below manager_employee in the reports_to hierarchy (any depth)."""
	rows = frappe.get_all("Employee", fields=["name", "reports_to"])
	children = {}
	for row in rows:
		if row.reports_to:
			children.setdefault(row.reports_to, []).append(row.name)

	result = []
	stack = [manager_employee]
	depth = 0
	while stack and depth < MAX_HIERARCHY_DEPTH:
		next_level = []
		for parent in stack:
			for child in children.get(parent, []):
				if child not in result:
					result.append(child)
					next_level.append(child)
		stack = next_level
		depth += 1
	return result


def is_in_manager_hierarchy(manager_employee, subject_employee):
	"""True if manager_employee is anywhere above subject_employee in reports_to chain."""
	current = subject_employee
	for _ in range(MAX_HIERARCHY_DEPTH):
		current = frappe.db.get_value("Employee", current, "reports_to")
		if not current:
			return False
		if current == manager_employee:
			return True
	return False


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return ""

	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if manager_employee:
		reportees = get_reportee_chain(manager_employee)
		if reportees:
			escaped = ", ".join(frappe.db.escape(name) for name in reportees)
			return f"`tabManager Note`.employee IN ({escaped})"

	# Employees must never see Manager Notes (including their own).
	return "1=0"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return True

	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not manager_employee:
		return False

	if not is_in_manager_hierarchy(manager_employee, doc.employee):
		return False

	if ptype in {"read", "print", "email", "export", "report", "create"}:
		return True

	# Append-only: managers cannot edit/delete existing notes
	return False


def can_create_manager_note(doc):
	user = frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(HR_ROLES):
		return True

	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not manager_employee:
		return False

	return is_in_manager_hierarchy(manager_employee, doc.employee)
