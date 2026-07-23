# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from volunteering.volunteering.employee_advance_controls import (
	advance_residual_amount,
	advance_residual_ratio,
	list_open_advances_for_employee,
)
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)


def execute(filters=None):
	filters = filters or {}
	columns = [
		{
			"label": "Advance",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Employee Advance",
			"width": 160,
		},
		{
			"label": "Employee",
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Advance Amount",
			"fieldname": "advance_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "Paid",
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "Claimed",
			"fieldname": "claimed_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "Returned",
			"fieldname": "return_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "Residual",
			"fieldname": "residual",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "Residual %",
			"fieldname": "residual_pct",
			"fieldtype": "Percent",
			"width": 100,
		},
	]

	settings = get_accounting_settings()
	threshold = flt(settings.get("advance_replenish_residual_pct"))
	if settings.get("advance_replenish_residual_pct") is None:
		threshold = 10.0

	employee_filter = filters.get("employee")
	if employee_filter:
		employees = [employee_filter]
	else:
		employees = sorted(
			{
				r.employee
				for r in frappe.get_all(
					"Employee Advance",
					filters={"docstatus": ["!=", 2]},
					fields=["employee"],
				)
				if r.employee
			}
		)

	data = []
	for employee in employees:
		if not employee:
			continue
		for row in list_open_advances_for_employee(employee):
			residual = advance_residual_amount(row)
			if residual <= 0:
				continue
			ratio = advance_residual_ratio(row)
			data.append(
				{
					"name": row.name,
					"employee": employee,
					"status": row.status,
					"advance_amount": row.advance_amount,
					"paid_amount": row.paid_amount,
					"claimed_amount": row.claimed_amount,
					"return_amount": row.return_amount,
					"residual": residual,
					"residual_pct": flt(ratio * 100, 2),
					"above_threshold": ratio > (threshold / 100.0),
				}
			)

	data.sort(key=lambda r: (-flt(r["residual"]), r["employee"] or "", r["name"] or ""))
	return columns, data
