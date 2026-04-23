# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    if not filters.get("event"):
        return [], []

    # 1. Get the dynamic columns from the child table for this event
    # We find all unique questions asked for this specific event
    questions = frappe.db.sql_list("""
        SELECT DISTINCT question 
        FROM `tabParticipation Extra Detail` ed
        JOIN `tabParticipation` p ON ed.parent = p.name
        WHERE p.event = %s AND p.docstatus < 2
    """, filters.get("event"))

    # 2. Define Base Columns
    columns = [
        {"label": "ID", "fieldname": "name", "fieldtype": "Link", "options": "Participation", "width": 120},
        {"label": "Volunteer", "fieldname": "temp_full_name", "fieldtype": "Data", "width": 150},
        {"label": "Residential Address", "fieldname": "temp_address", "fieldtype": "Small Text", "width": 200}
    ]

    # 3. Add Dynamic Columns based on questions found
    for q in questions:
        # We slugify the question to use as a fieldname (e.g., "Kits Requested")
        fieldname = q.replace(" ", "_").lower()
        columns.append({
            "label": q,
            "fieldname": fieldname,
            "fieldtype": "Data",
            "width": 150
        })

    # Add Comments at the end
    columns.append({"label": "Comments", "fieldname": "comments", "fieldtype": "Small Text", "width": 200})

    # 4. Fetch Data
    participations = frappe.get_all("Participation", 
        filters={"event": filters.get("event"), "docstatus": ["<", 2]},
        fields=["name", "temp_full_name", "temp_address", "comments"]
    )

    res = []
    for p in participations:
        row = p
        # Fetch child table entries for this specific participation
        extra_data = frappe.get_all("Participation Extra Detail",
            filters={"parent": p.name},
            fields=["question", "answer"]
        )
        
        # Map child table answers to the dynamic fieldnames
        for d in extra_data:
            fname = d.question.replace(" ", "_").lower()
            row[fname] = d.answer
            
        res.append(row)

    return columns, res


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Column 1"),
			"fieldname": "column_1",
			"fieldtype": "Data",
		},
		{
			"label": _("Column 2"),
			"fieldname": "column_2",
			"fieldtype": "Int",
		},
	]


def get_data() -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	return [
		["Row 1", 1],
		["Row 2", 2],
	]
