"""Read-only, session-bound employee profile for the staff portal."""

import frappe
from frappe import _

# Never serialize the Employee document wholesale: it also holds payroll,
# identity documents, banking and administrative fields.
PROFILE_FIELDS = (
	"name",
	"employee_name",
	"status",
	"date_of_joining",
	"designation",
	"grade",
	"employment_type",
	"branch",
	"reports_to",
	"expense_approver",
	"cell_number",
	"company_email",
	"personal_email",
	"person_to_be_contacted",
	"emergency_phone_number",
	"relation",
)


@frappe.whitelist(methods=["POST"])
def get_my_profile():
	"""Return only the current user's account and linked employee details.

	No target user/employee argument is accepted. This narrowly scoped lookup
	does not grant generic Employee or Account read permissions.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to view your profile."), frappe.PermissionError)

	account = frappe.db.get_value("User", user, ["full_name", "email", "user_type"], as_dict=True)
	if not account:
		frappe.throw(_("Your user account could not be found."), frappe.PermissionError)
	account = {
		"user_id": user,
		**{field: account.get(field) for field in ("full_name", "email", "user_type")},
	}
	meta = frappe.get_meta("Employee")
	fields = [field for field in PROFILE_FIELDS if field == "name" or meta.has_field(field)]
	# The identity filter is derived solely from the authenticated session.
	stored = frappe.db.get_value("Employee", {"user_id": user}, fields, as_dict=True)
	employee = {field: stored.get(field) for field in fields} if stored else None
	if employee:
		manager = employee.get("reports_to")
		employee["reporting_manager_name"] = (
			frappe.db.get_value("Employee", manager, "employee_name") if manager else None
		)
		approver = employee.get("expense_approver")
		employee["expense_approver_name"] = (
			frappe.db.get_value("User", approver, "full_name") if approver else None
		)
	return {"account": account, "employee": employee}
