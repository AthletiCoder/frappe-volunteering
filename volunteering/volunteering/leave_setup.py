import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import get_year_ending, get_year_start, getdate, nowdate

from volunteering.volunteering.custom_fields import CUSTOM_FIELDS

LEAVE_TYPE_NAME = "Privilege Leave"
LEAVE_POLICY_TITLE = "Sevamrita Standard Leave Policy"
ANNUAL_LEAVE_ALLOCATION = 60
CARRY_FORWARD_MAX = 5


def after_migrate():
	setup_custom_fields()
	setup_hr_masters()
	assign_missing_leave_policies()


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def setup_hr_masters():
	configure_hr_settings()
	ensure_leave_type()
	companies = frappe.get_all("Company", pluck="name")
	if not companies:
		return

	for company in companies:
		leave_period = ensure_leave_period(company)
		ensure_leave_policy(company)
		update_leave_policy_settings(company, leave_period)


def configure_hr_settings():
	if not frappe.db.exists("DocType", "HR Settings"):
		return

	hr_settings = frappe.get_single("HR Settings")
	hr_settings.restrict_backdated_leave_application = 0
	hr_settings.leave_approver_mandatory_in_leave_application = 1
	hr_settings.save(ignore_permissions=True)


def ensure_leave_type():
	if frappe.db.exists("Leave Type", LEAVE_TYPE_NAME):
		leave_type = frappe.get_doc("Leave Type", LEAVE_TYPE_NAME)
		leave_type.is_carry_forward = 1
		leave_type.maximum_carry_forwarded_leaves = CARRY_FORWARD_MAX
		leave_type.include_holiday = 1
		leave_type.allow_encashment = 0
		leave_type.is_lwp = 0
		leave_type.save(ignore_permissions=True)
		return leave_type.name

	leave_type = frappe.get_doc(
		{
			"doctype": "Leave Type",
			"leave_type_name": LEAVE_TYPE_NAME,
			"is_carry_forward": 1,
			"maximum_carry_forwarded_leaves": CARRY_FORWARD_MAX,
			"include_holiday": 1,
			"allow_encashment": 0,
			"is_lwp": 0,
		}
	)
	leave_type.insert(ignore_permissions=True)
	return leave_type.name


def ensure_leave_period(company):
	year_start = get_year_start(nowdate())
	year_end = get_year_ending(nowdate())

	existing = frappe.db.get_value(
		"Leave Period",
		{
			"company": company,
			"from_date": year_start,
			"to_date": year_end,
		},
		"name",
	)
	if existing:
		return existing

	leave_period = frappe.get_doc(
		{
			"doctype": "Leave Period",
			"company": company,
			"from_date": year_start,
			"to_date": year_end,
			"is_active": 1,
		}
	)
	leave_period.insert(ignore_permissions=True)
	return leave_period.name


def ensure_leave_policy(company):
	existing = frappe.db.get_value("Leave Policy", {"title": LEAVE_POLICY_TITLE}, "name")
	if existing:
		policy = frappe.get_doc("Leave Policy", existing)
		if not policy.leave_policy_details:
			policy.append(
				"leave_policy_details",
				{"leave_type": LEAVE_TYPE_NAME, "annual_allocation": ANNUAL_LEAVE_ALLOCATION},
			)
			policy.save(ignore_permissions=True)
		return existing

	policy = frappe.get_doc(
		{
			"doctype": "Leave Policy",
			"title": LEAVE_POLICY_TITLE,
			"leave_policy_details": [
				{
					"leave_type": LEAVE_TYPE_NAME,
					"annual_allocation": ANNUAL_LEAVE_ALLOCATION,
				}
			],
		}
	)
	policy.insert(ignore_permissions=True)
	return policy.name


def update_leave_policy_settings(company, leave_period):
	if not frappe.db.exists("DocType", "Leave Policy Settings"):
		return

	settings = frappe.get_single("Leave Policy Settings")
	settings.default_leave_type = LEAVE_TYPE_NAME
	settings.default_leave_policy = frappe.db.get_value(
		"Leave Policy", {"title": LEAVE_POLICY_TITLE}, "name"
	)
	settings.default_leave_period = leave_period
	settings.default_company = company
	settings.save(ignore_permissions=True)


def assign_default_leave_policy(doc, method=None):
	if doc.status != "Active":
		return

	assign_leave_policy_to_employee(doc.name)


def assign_missing_leave_policies():
	employees = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
	for employee in employees:
		try:
			assign_leave_policy_to_employee(employee)
		except Exception:
			frappe.log_error(
				title=f"Leave policy assignment failed for {employee}",
				message=frappe.get_traceback(),
			)


def assign_leave_policy_to_employee(employee):
	settings = get_setup_settings()
	leave_policy = settings.get("default_leave_policy")
	leave_period = settings.get("default_leave_period")

	if not leave_policy or not leave_period:
		setup_hr_masters()
		settings = get_setup_settings()
		leave_policy = settings.get("default_leave_policy")
		leave_period = settings.get("default_leave_period")

	if not leave_policy or not leave_period:
		return

	if has_leave_policy_assignment(employee, leave_period):
		return

	assignment = frappe.get_doc(
		{
			"doctype": "Leave Policy Assignment",
			"employee": employee,
			"leave_policy": leave_policy,
			"assignment_based_on": "Leave Period",
			"leave_period": leave_period,
			"carry_forward": 1,
		}
	)
	assignment.insert(ignore_permissions=True)
	assignment.submit()


def has_leave_policy_assignment(employee, leave_period):
	from_date, to_date = frappe.db.get_value("Leave Period", leave_period, ["from_date", "to_date"])
	if not from_date or not to_date:
		return False

	return frappe.db.exists(
		"Leave Policy Assignment",
		{
			"employee": employee,
			"docstatus": 1,
			"effective_from": ["<=", getdate(to_date)],
			"effective_to": [">=", getdate(from_date)],
		},
	)


def get_setup_settings():
	if frappe.db.exists("DocType", "Leave Policy Settings"):
		return frappe.get_single("Leave Policy Settings").as_dict()

	return {}
