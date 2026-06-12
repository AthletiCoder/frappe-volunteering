# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, getdate


def execute(filters=None):
	filters = filters or {}
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	if not from_date or not to_date:
		frappe.throw("From Date and To Date are required.")

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	if from_date > to_date:
		frappe.throw("From Date cannot be after To Date.")

	columns = get_columns()
	data = get_data(from_date, to_date, filters.get("status"))
	return columns, data


def get_columns():
	return [
		{
			"label": "Employee",
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": "Employee Name",
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Date",
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def get_data(from_date, to_date, status_filter=None):
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name"],
	)

	logs = {
		(log.employee, getdate(log.date)): log.name
		for log in frappe.get_all(
			"Daily Work Log",
			filters={
				"docstatus": 1,
				"date": ["between", [from_date, to_date]],
			},
			fields=["name", "employee", "date"],
		)
	}

	leaves = get_leave_map(from_date, to_date)
	rows = []
	current_date = from_date

	while current_date <= to_date:
		for employee in employees:
			key = (employee.name, current_date)
			if key in leaves:
				status = "On Leave"
			elif key in logs:
				status = "Present"
			else:
				status = "Missing Log"

			if status_filter and status != status_filter:
				continue

			rows.append(
				{
					"employee": employee.name,
					"employee_name": employee.employee_name,
					"date": current_date,
					"status": status,
				}
			)

		current_date = add_days(current_date, 1)

	return rows


def get_leave_map(from_date, to_date):
	leave_map = {}
	leave_applications = frappe.get_all(
		"Leave Application",
		filters={
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		fields=["employee", "from_date", "to_date"],
	)

	for leave in leave_applications:
		current_date = getdate(leave.from_date)
		end_date = getdate(leave.to_date)

		while current_date <= end_date:
			if from_date <= current_date <= to_date:
				leave_map[(leave.employee, current_date)] = True
			current_date = add_days(current_date, 1)

	return leave_map
