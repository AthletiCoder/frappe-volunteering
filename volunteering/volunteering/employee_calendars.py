"""Employee holiday calendars keep payroll and HRMS leave counts in agreement."""
from datetime import date, timedelta

import frappe
from frappe.utils import getdate, nowdate
from volunteering.volunteering.hr_policy import policy_on


def _base_holidays(employee, year):
	person = frappe.db.get_value("Employee", employee, ["holiday_list", "company"], as_dict=True)
	base = person.holiday_list or frappe.db.get_value("Company", person.company, "default_holiday_list")
	assignments = [row for row in frappe.get_all("Holiday List Assignment", filters={"assigned_to": ["in", [employee, person.company]],
		"docstatus": 1, "from_date": ["<=", date(year, 12, 31)]}, fields=["assigned_to", "from_date", "holiday_list"], order_by="from_date desc")
		if not row.holiday_list.startswith("SF Calendar ")]
	names = {row.holiday_list for row in assignments}
	if base and not base.startswith("SF Calendar "): names.add(base)
	if not names: return {}
	by_list = {}
	for row in frappe.get_all("Holiday", filters={"parent": ["in", list(names)], "holiday_date": ["between", [date(year, 1, 1), date(year, 12, 31)]]}, fields=["parent", "holiday_date", "weekly_off", "description"]):
		by_list.setdefault(row.parent, {})[getdate(row.holiday_date)] = row
	rows = {}; day = date(year, 1, 1)
	while day.year == year:
		own = next((row.holiday_list for row in assignments if row.assigned_to == employee and getdate(row.from_date) <= day), None)
		company = next((row.holiday_list for row in assignments if row.assigned_to == person.company and getdate(row.from_date) <= day), None)
		row = by_list.get(own or company or base, {}).get(day)
		if row: rows[day] = row
		day += timedelta(days=1)
	return rows


def calendar_days(employee, year):
	cache = getattr(frappe.local, "sf_employee_calendars", None)
	if cache is None: cache = frappe.local.sf_employee_calendars = {}
	key = (employee, year)
	if key in cache: return cache[key]
	base = _base_holidays(employee, year)
	swaps = frappe.get_all("Staff Time Request", filters={"employee": employee, "request_type": "Weekly Off Swap", "status": "Approved",
		"from_date": ["between", [date(year-1, 12, 25), date(year+1, 1, 7)]]}, fields=["from_date", "to_date"]) if frappe.db.exists("DocType", "Staff Time Request") else []
	working = {getdate(row.from_date) for row in swaps}; off = {getdate(row.to_date) for row in swaps}
	rows = {}; day = date(year, 1, 1)
	while day.year == year:
		policy = policy_on(day); original = base.get(day)
		# The charter's twelve fixed holidays replace inherited non-weekly
		# holidays. Otherwise old calendars could silently turn optional days
		# (for example Christmas) into an extra fixed holiday for everybody.
		if original and not original.weekly_off and not policy.get("charter_enabled"):
			rows[day] = {"holiday_date": day, "weekly_off": 0, "description": original.description or "Holiday"}
		elif day in off:
			rows[day] = {"holiday_date": day, "weekly_off": 1, "description": "Approved weekly-off swap"}
		elif day not in working and (day.weekday() == policy["weekly_off_day"] or (policy.get("_legacy") and original)):
			rows[day] = {"holiday_date": day, "weekly_off": 1, "description": "Weekly Off"}
		day += timedelta(days=1)
	if frappe.db.exists("DocType", "HR Holiday"):
		company=frappe.db.get_value("Employee",employee,"company")
		for holiday in frappe.get_all("HR Holiday",filters={"company":company,"kind":"Fixed","enabled":1,"holiday_date":["between",[date(year,1,1),date(year,12,31)]]},fields=["holiday_date","holiday_name"]):
			day=getdate(holiday.holiday_date)
			if policy_on(day)["charter_enabled"]:rows[day]={"holiday_date":day,"weekly_off":0,"description":holiday.holiday_name}
	cache[key] = rows
	return rows


def holiday_on(employee, day):
	day = getdate(day)
	return calendar_days(employee, day.year).get(day)


def clear_calendar_cache():
	frappe.local.sf_employee_calendars = {}


def sync_employee_calendar(employee, year=None):
	year = int(year or getdate(nowdate()).year)
	policies = frappe.get_all("HR Policy Revision", filters={"effective_from": ["<=", date(year, 12, 31)]}, pluck="effective_from")
	if not policies: return
	first = max(date(year, 1, 1), min(getdate(day) for day in policies))
	rows = calendar_days(employee, year)
	name = f"SF Calendar {employee} {year}"
	doc = frappe.get_doc("Holiday List", name) if frappe.db.exists("Holiday List", name) else frappe.get_doc({
		"doctype": "Holiday List", "holiday_list_name": name, "from_date": date(year, 1, 1), "to_date": date(year, 12, 31)})
	current = {(getdate(row.holiday_date), int(row.weekly_off or 0), row.description or "") for row in doc.holidays}
	wanted = {(day, row["weekly_off"], row["description"]) for day, row in rows.items()}
	if current != wanted or doc.is_new():
		doc.set("holidays", list(rows.values())); doc.save(ignore_permissions=True)
	if not frappe.db.exists("Holiday List Assignment", {"applicable_for": "Employee", "assigned_to": employee, "holiday_list": name, "docstatus": 1}):
		frappe.get_doc({"doctype": "Holiday List Assignment", "applicable_for": "Employee", "assigned_to": employee,
			"holiday_list": name, "from_date": first}).insert(ignore_permissions=True).submit()
	return name


def sync_all_calendars():
	for employee in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
		for year in (getdate(nowdate()).year, getdate(nowdate()).year + 1):
			sync_employee_calendar(employee, year)


def prepare_salary_calendar(doc, method=None):
	if doc.employee:
		for year in range(getdate(doc.start_date or nowdate()).year, getdate(doc.end_date or nowdate()).year + 1):
			sync_employee_calendar(doc.employee, year)
		if not doc.get("salary_slip_based_on_timesheet") and policy_on(doc.end_date).get("attendance_based_payroll"):
			from volunteering.volunteering.attendance_service import process_employee_attendance
			day, end = getdate(doc.start_date or nowdate()), min(getdate(doc.end_date or nowdate()), getdate(nowdate()))
			while day <= end:
				if policy_on(day).get("_revision"): process_employee_attendance(doc.employee, day)
				day += timedelta(days=1)


def validate_salary_policy(doc, method=None):
	from frappe import _
	from volunteering.volunteering.hr_policy import applies_to_employee, deadline_for_log
	if not doc.employee or not applies_to_employee(doc.employee) or not policy_on(doc.end_date).get("attendance_based_payroll"): return
	if doc.get("salary_slip_based_on_timesheet"): return
	for doctype, filters in (("Leave Application", {"docstatus": 0}), ("Staff Time Request", {"request_type": ["in", ["Weekly Off Swap", "WFH", "Attendance Correction"]]})):
		if frappe.db.exists(doctype, {**filters, "employee": doc.employee, "status": "Open", "from_date": ["<=", doc.end_date], "to_date": [">=", doc.start_date]}):
			frappe.throw(_("Resolve this employee's open leave or attendance requests before submitting salary."))
	if policy_on(doc.end_date).get("charter_enabled"):
		for row in doc.get("deductions") or []:
			if row.salary_component in {"SF Employee PF","SF Professional Tax"} and row.amount:
				if not frappe.db.get_value("Salary Component Account",{"parent":row.salary_component,"company":doc.company},"account"):
					frappe.throw(_("Configure PF and Professional Tax liability ledgers in the People centre before submitting salary."))
	day, end = getdate(doc.start_date), getdate(doc.end_date)
	person = frappe.db.get_value("Employee", doc.employee, ["date_of_joining", "relieving_date"], as_dict=True)
	day = max(day, getdate(person.date_of_joining))
	if person.relieving_date: end = min(end, getdate(person.relieving_date))
	while day <= end:
		if policy_on(day).get("_revision") and not holiday_on(doc.employee, day):
			marked = frappe.db.exists("Attendance", {"employee": doc.employee, "attendance_date": day, "docstatus": 1})
			if not marked and getdate(nowdate()) < deadline_for_log(day):
				frappe.throw(_("Work logging is still open for {0}. Wait for the logging window or resolve the attendance before submitting salary.").format(day))
		day += timedelta(days=1)
