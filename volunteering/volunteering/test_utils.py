import random

import frappe
from frappe.utils import add_days, get_year_ending, get_year_start, getdate, nowdate

HOLIDAY_LIST_NAME = "_Test Volunteering Holiday List"
TEST_LEAVE_TYPE = "_Test Volunteering Leave"
TEST_PROJECT_NAME = "_Test Volunteering Project"
TEST_EMPLOYEE_EMAIL = "volunteering_test@example.com"


def unique_mobile(prefix="98"):
    return f"+91-{prefix}{random.randint(10**7, 10**8 - 1)}"


def get_test_company():
	return frappe.db.get_value("Company", {}, "name")


def ensure_holiday_list(company=None):
	company = company or get_test_company()
	today = getdate()
	from_date = get_year_start(today)
	to_date = get_year_ending(today)

	if frappe.db.exists("Holiday List", HOLIDAY_LIST_NAME):
		holiday_list = frappe.get_doc("Holiday List", HOLIDAY_LIST_NAME)
		if getdate(holiday_list.from_date) <= today <= getdate(holiday_list.to_date):
			_ensure_holiday_list_assignment("Company", company, HOLIDAY_LIST_NAME, company)
			return HOLIDAY_LIST_NAME

	frappe.delete_doc_if_exists("Holiday List", HOLIDAY_LIST_NAME, force=True)
	holiday_list = frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": HOLIDAY_LIST_NAME,
			"from_date": from_date,
			"to_date": to_date,
		}
	).insert(ignore_permissions=True)
	holiday_list.weekly_off = "Sunday"
	holiday_list.get_weekly_off_dates()
	holiday_list.save(ignore_permissions=True)

	frappe.db.set_value("Company", company, "default_holiday_list", HOLIDAY_LIST_NAME)
	_ensure_holiday_list_assignment("Company", company, HOLIDAY_LIST_NAME, company)
	return HOLIDAY_LIST_NAME


def ensure_employee_holiday_list(employee, company=None):
	company = company or frappe.db.get_value("Employee", employee, "company")
	holiday_list = ensure_holiday_list(company)
	_ensure_holiday_list_assignment("Employee", employee, holiday_list, company)
	return holiday_list


def ensure_holiday_list_for_employee(employee, as_on_date):
	"""Ensure the employee has a holiday list assignment valid on as_on_date."""
	as_on_date = getdate(as_on_date)
	company = frappe.db.get_value("Employee", employee, "company")
	holiday_list_name = f"_Test Holidays {frappe.scrub(employee)}"

	if not frappe.db.exists("Holiday List", holiday_list_name):
		frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": holiday_list_name,
				"from_date": add_days(as_on_date, -365),
				"to_date": add_days(as_on_date, 365),
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists(
		"Holiday List Assignment",
		{
			"applicable_for": "Employee",
			"assigned_to": employee,
			"docstatus": 1,
		},
	):
		assignment = frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Employee",
				"assigned_to": employee,
				"holiday_list": holiday_list_name,
				"from_date": add_days(as_on_date, -365),
				"employee_company": company,
			}
		)
		assignment.insert(ignore_permissions=True)
		assignment.submit()


def _ensure_holiday_list_assignment(applicable_for, assigned_to, holiday_list, company):
	if frappe.db.exists(
		"Holiday List Assignment",
		{
			"applicable_for": applicable_for,
			"assigned_to": assigned_to,
			"holiday_list": holiday_list,
			"docstatus": 1,
		},
	):
		return

	from_date = frappe.db.get_value("Holiday List", holiday_list, "from_date")
	assignment = frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"applicable_for": applicable_for,
			"assigned_to": assigned_to,
			"holiday_list": holiday_list,
			"employee_company": company,
			"from_date": from_date,
		}
	)
	assignment.insert(ignore_permissions=True)
	assignment.submit()


def _create_test_user(email):
	if frappe.db.exists("User", email):
		return

	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Volunteering Test",
			"new_password": "password",
			"send_welcome_email": 0,
			"roles": [{"role": "Employee"}],
		}
	).insert(ignore_permissions=True)


def get_or_create_test_employee():
	employee = (
		frappe.db.get_value("Employee", {"user_id": TEST_EMPLOYEE_EMAIL, "status": "Active"}, "name")
		or frappe.db.get_value("Employee", {"first_name": "Volunteering Test", "status": "Active"}, "name")
		or frappe.db.get_value("Employee", {"status": "Active"}, "name")
	)

	if not employee:
		company = get_test_company()
		ensure_holiday_list(company)
		_create_test_user(TEST_EMPLOYEE_EMAIL)
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Volunteering Test",
				"company": company,
				"user_id": TEST_EMPLOYEE_EMAIL,
				"company_email": TEST_EMPLOYEE_EMAIL,
				"status": "Active",
				"date_of_birth": add_days(nowdate(), -10000),
				"date_of_joining": add_days(nowdate(), -90),
				"gender": "Male",
			}
		).insert(ignore_permissions=True).name

	ensure_employee_holiday_list(employee)
	return employee


def make_test_phone(local_number=None):
	from volunteering.volunteering.doctype.volunteer.volunteer import format_mobile_number

	if local_number is None:
		return f"+91-9{random.randint(100000000, 999999999)}"

	digits = "".join(ch for ch in str(local_number) if ch.isdigit())
	if len(digits) < 10:
		digits = f"9{digits.zfill(9)}"[:10]
	elif len(digits) > 10:
		digits = digits[-10:]

	if digits[0] not in "6789":
		digits = f"9{digits[1:]}"

	return format_mobile_number(digits)


def get_or_create_allocatable_leave_type(name=TEST_LEAVE_TYPE):
	if frappe.db.exists("Leave Type", name):
		if frappe.db.get_value("Leave Type", name, "is_lwp"):
			frappe.db.set_value("Leave Type", name, "is_lwp", 0)
		return name

	frappe.get_doc(
		{
			"doctype": "Leave Type",
			"leave_type_name": name,
			"is_lwp": 0,
		}
	).insert(ignore_permissions=True)
	return name


def ensure_leave_allocation(employee, leave_type, from_date=None, to_date=None, leaves=10):
	from_date = from_date or add_days(nowdate(), -60)
	to_date = to_date or add_days(nowdate(), 365)

	existing = frappe.db.exists(
		"Leave Allocation",
		{
			"employee": employee,
			"leave_type": leave_type,
			"docstatus": 1,
			"from_date": ["<=", from_date],
			"to_date": [">=", to_date],
		},
	)
	if existing:
		return existing

	allocation = frappe.get_doc(
		{
			"doctype": "Leave Allocation",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"new_leaves_allocated": leaves,
		}
	)
	allocation.insert(ignore_permissions=True)
	allocation.submit()
	return allocation.name


def get_or_create_test_project(employee):
	if frappe.db.exists("Project", {"project_name": TEST_PROJECT_NAME}):
		return frappe.db.get_value("Project", {"project_name": TEST_PROJECT_NAME}, "name")

	company = frappe.db.get_value("Employee", employee, "company")
	return frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": TEST_PROJECT_NAME,
			"company": company,
		}
	).insert(ignore_permissions=True).name
