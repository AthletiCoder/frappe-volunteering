import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate, nowdate

from volunteering.volunteering.custom_fields import CUSTOM_FIELDS
from volunteering.patches.setup_attendance_holiday_status import ensure_holiday_status_option

LEAVE_TYPE_NAME = "Privilege Leave"
LWP_TYPE_NAME = "Leave Without Pay"
LEAVE_POLICY_TITLE = "Sevamrita Standard Leave Policy"
ANNUAL_LEAVE_ALLOCATION = 30
WEEKLY_OFF_DAY = 2  # Wednesday (Python weekday: Mon=0)


def after_migrate():
	setup_custom_fields()
	ensure_holiday_status_option()
	try:
		from volunteering.volunteering.employment_type import ensure_employment_type

		ensure_employment_type()
		setup_hr_masters()
		ensure_wednesday_weekly_off()
		assign_missing_leave_policies()
		_setup_attendance_request_permissions()
		from volunteering.volunteering.leave_pending import backfill_leave_approvers_from_reports_to

		backfill_leave_approvers_from_reports_to()
	except Exception:
		frappe.log_error(title="Leave setup after_migrate failed", message=frappe.get_traceback())


def _setup_attendance_request_permissions():
	from volunteering.volunteering.attendance_request_permissions import (
		ensure_attendance_request_permissions,
	)

	ensure_attendance_request_permissions()


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def setup_hr_masters():
	configure_hr_settings()
	ensure_leave_type()
	ensure_lwp_leave_type()
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

	# Prefer set_single_value to avoid Property Setter / Redis side-effects on full save
	frappe.db.set_single_value("HR Settings", "restrict_backdated_leave_application", 0)
	frappe.db.set_single_value("HR Settings", "leave_approver_mandatory_in_leave_application", 1)
	if frappe.db.has_column("Singles", "doctype") or True:
		try:
			frappe.db.set_single_value("HR Settings", "prevent_self_leave_approval", 1)
		except Exception:
			hr_settings = frappe.get_single("HR Settings")
			if hasattr(hr_settings, "prevent_self_leave_approval"):
				hr_settings.db_set("prevent_self_leave_approval", 1, update_modified=False)


def ensure_leave_type():
	values = {
		"is_carry_forward": 0,
		"include_holiday": 0,
		"allow_encashment": 0,
		"is_lwp": 0,
		"allow_negative": 1,
		"is_earned_leave": 1,
		"earned_leave_frequency": "Monthly",
		"allocate_on_day": "First Day",
		"rounding": "0.25",
		"max_leaves_allowed": ANNUAL_LEAVE_ALLOCATION,
	}

	if frappe.db.exists("Leave Type", LEAVE_TYPE_NAME):
		leave_type = frappe.get_doc("Leave Type", LEAVE_TYPE_NAME)
		leave_type.update(values)
		leave_type.save(ignore_permissions=True)
		return leave_type.name

	leave_type = frappe.get_doc({"doctype": "Leave Type", "leave_type_name": LEAVE_TYPE_NAME, **values})
	leave_type.insert(ignore_permissions=True)
	return leave_type.name


def ensure_lwp_leave_type():
	if frappe.db.exists("Leave Type", LWP_TYPE_NAME):
		leave_type = frappe.get_doc("Leave Type", LWP_TYPE_NAME)
		leave_type.is_lwp = 1
		leave_type.allow_encashment = 0
		leave_type.is_carry_forward = 0
		leave_type.save(ignore_permissions=True)
		return leave_type.name

	leave_type = frappe.get_doc(
		{
			"doctype": "Leave Type",
			"leave_type_name": LWP_TYPE_NAME,
			"is_lwp": 1,
			"allow_encashment": 0,
			"is_carry_forward": 0,
		}
	)
	leave_type.insert(ignore_permissions=True)
	return leave_type.name


def get_fy_dates(as_of=None):
	"""Indian financial year: 1 Apr – 31 Mar."""
	as_of = getdate(as_of or nowdate())
	if as_of.month >= 4:
		start = as_of.replace(month=4, day=1)
		end = as_of.replace(year=as_of.year + 1, month=3, day=31)
	else:
		start = as_of.replace(year=as_of.year - 1, month=4, day=1)
		end = as_of.replace(month=3, day=31)
	return start, end


def ensure_leave_period(company):
	year_start, year_end = get_fy_dates()

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
		frappe.db.set_value("Leave Period", existing, "is_active", 1)
		return existing

	# Reuse any overlapping period for this company in the FY window
	overlap = frappe.db.sql(
		"""
		SELECT name FROM `tabLeave Period`
		WHERE company = %s
			AND from_date <= %s AND to_date >= %s
		ORDER BY is_active DESC, creation DESC
		LIMIT 1
		""",
		(company, year_end, year_start),
	)
	if overlap:
		name = overlap[0][0]
		frappe.db.set_value(
			"Leave Period",
			name,
			{"from_date": year_start, "to_date": year_end, "is_active": 1},
		)
		return name

	# Deactivate other active periods for a clean FY switch
	for name in frappe.get_all(
		"Leave Period",
		filters={"company": company, "is_active": 1},
		pluck="name",
	):
		frappe.db.set_value("Leave Period", name, "is_active", 0)

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
		updated = False
		if not policy.leave_policy_details:
			policy.append(
				"leave_policy_details",
				{"leave_type": LEAVE_TYPE_NAME, "annual_allocation": ANNUAL_LEAVE_ALLOCATION},
			)
			updated = True
		else:
			for row in policy.leave_policy_details:
				if row.leave_type == LEAVE_TYPE_NAME and flt_or(row.annual_allocation) != ANNUAL_LEAVE_ALLOCATION:
					row.annual_allocation = ANNUAL_LEAVE_ALLOCATION
					updated = True
		if updated:
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


def flt_or(value):
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def update_leave_policy_settings(company, leave_period):
	if not frappe.db.exists("DocType", "Leave Policy Settings"):
		return

	settings = frappe.get_single("Leave Policy Settings")
	settings.default_leave_type = LEAVE_TYPE_NAME
	settings.leave_without_pay_type = LWP_TYPE_NAME
	settings.default_leave_policy = frappe.db.get_value(
		"Leave Policy", {"title": LEAVE_POLICY_TITLE}, "name"
	)
	settings.default_leave_period = leave_period
	settings.default_company = company
	settings.emergency_max_consecutive_days = 3
	settings.director_approval_days = 7
	settings.planned_leave_advance_days = 0  # replaced by N-for-N notice
	settings.save(ignore_permissions=True)


def assign_default_leave_policy(doc, method=None):
	if doc.status != "Active":
		return

	from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE, is_unpaid_employee

	if is_unpaid_employee(doc.name) or getattr(doc, "employment_type", None) == UNPAID_EMPLOYMENT_TYPE:
		return

	assign_leave_policy_to_employee(doc.name)


def assign_missing_leave_policies():
	from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employment_type"],
	)
	for employee in employees:
		if employee.employment_type == UNPAID_EMPLOYMENT_TYPE:
			continue
		try:
			assign_leave_policy_to_employee(employee.name)
		except Exception:
			frappe.log_error(
				title=f"Leave policy assignment failed for {employee.name}",
				message=frappe.get_traceback(),
			)


def assign_leave_policy_to_employee(employee):
	from volunteering.volunteering.employment_type import is_unpaid_employee

	if is_unpaid_employee(employee):
		return

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
			"carry_forward": 0,
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


def ensure_wednesday_weekly_off():
	"""Ensure each company's holiday list marks Wednesday as weekly off for the FY."""
	year_start, year_end = get_fy_dates()
	companies = frappe.get_all("Company", fields=["name", "default_holiday_list"])

	for company in companies:
		holiday_list = company.default_holiday_list
		if not holiday_list:
			holiday_list = _ensure_company_holiday_list(company.name, year_start, year_end)
			frappe.db.set_value("Company", company.name, "default_holiday_list", holiday_list)

		_ensure_weekly_offs(holiday_list, year_start, year_end)
		_ensure_holiday_list_assignment(company.name, holiday_list, year_start)


def _ensure_holiday_list_assignment(company, holiday_list, from_date):
	"""HRMS v16 resolves holiday lists via Holiday List Assignment."""
	if not frappe.db.exists("DocType", "Holiday List Assignment"):
		return

	existing = frappe.db.exists(
		"Holiday List Assignment",
		{"assigned_to": company, "docstatus": 1},
	)
	if existing:
		return

	assignment = frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"applicable_for": "Company",
			"assigned_to": company,
			"holiday_list": holiday_list,
			"from_date": from_date,
		}
	)
	assignment.insert(ignore_permissions=True)
	assignment.submit()


def _ensure_company_holiday_list(company, year_start, year_end):
	name = f"{company} Holidays FY {year_start.year}-{str(year_end.year)[-2:]}"
	if frappe.db.exists("Holiday List", name):
		return name

	doc = frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": name,
			"from_date": year_start,
			"to_date": year_end,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_weekly_offs(holiday_list_name, year_start, year_end):
	from datetime import timedelta

	doc = frappe.get_doc("Holiday List", holiday_list_name)
	existing = {getdate(row.holiday_date) for row in doc.holidays if row.weekly_off}

	current = getdate(year_start)
	end = getdate(year_end)
	added = False
	while current <= end:
		if current.weekday() == WEEKLY_OFF_DAY and current not in existing:
			doc.append(
				"holidays",
				{
					"holiday_date": current,
					"description": "Weekly Off",
					"weekly_off": 1,
				},
			)
			added = True
		current += timedelta(days=1)

	if added:
		doc.flags.ignore_validate = True
		doc.save(ignore_permissions=True)


def get_setup_settings():
	if frappe.db.exists("DocType", "Leave Policy Settings"):
		return frappe.get_single("Leave Policy Settings").as_dict()

	return {}
