# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Restrict Attendance list/form to self + reportees (employees)."""

import frappe

HR_ROLES = {"HR Manager", "HR User", "System Manager"}
# Only HR sees all attendance rows. Employee (+ other ops roles) limited to self + reportees.
FULL_ACCESS_ROLES = HR_ROLES


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles.intersection(FULL_ACCESS_ROLES):
		return ""

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return "1=0"

	own = frappe.db.escape(employee)
	return (
		f"(`tabAttendance`.employee = {own} "
		f"OR `tabAttendance`.employee IN ("
		f"SELECT name FROM `tabEmployee` WHERE reports_to = {own}))"
	)


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(FULL_ACCESS_ROLES):
		return True

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	is_own = doc.employee == employee
	is_manager = frappe.db.get_value("Employee", doc.employee, "reports_to") == employee
	return is_own or is_manager
