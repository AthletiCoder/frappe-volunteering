import random

import frappe
from frappe.utils import add_days, getdate


def unique_mobile(prefix="98"):
    return f"+91-{prefix}{random.randint(10**7, 10**8 - 1)}"


def get_or_create_allocatable_leave_type(name="_Test Volunteering Leave"):
    if frappe.db.exists("Leave Type", name):
        return name

    return (
        frappe.get_doc(
            {
                "doctype": "Leave Type",
                "leave_type_name": name,
                "is_lwp": 0,
            }
        )
        .insert(ignore_permissions=True)
        .name
    )


def ensure_holiday_list_for_employee(employee, as_on_date):
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
