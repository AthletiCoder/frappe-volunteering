# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import scrub


def execute(filters=None):
    filters = filters or {}
    event = filters.get("event")
    if not event:
        return [], []

    # 1. Get the dynamic columns from the child table for this event
    # We find all unique questions asked for this specific event
    questions = frappe.db.sql_list(
        """
        SELECT DISTINCT question 
        FROM `tabParticipation Extra Detail` ed
        JOIN `tabParticipation` p ON ed.parent = p.name
        WHERE p.event = %s AND p.docstatus < 2
    """,
        event,
    )

    # 2. Define Base Columns
    columns = [
        {"label": "ID", "fieldname": "name", "fieldtype": "Link", "options": "Participation", "width": 120},
        {"label": "Volunteer", "fieldname": "temp_full_name", "fieldtype": "Data", "width": 150},
        {"label": "Phone", "fieldname": "temp_phone", "fieldtype": "Phone", "width": 120},
        {"label": "Residential Address", "fieldname": "temp_address", "fieldtype": "Small Text", "width": 200}
    ]

    # 3. Add Dynamic Columns based on questions found
    for q in questions:
        # We slugify the question to use as a fieldname (e.g., "Kits Requested")
        fieldname = scrub(q)
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
        filters={"event": event, "docstatus": ["<", 2]},
        fields=["name", "temp_full_name", "temp_phone","temp_address", "comments"]
    )

    participation_names = [row.name for row in participations]
    detail_by_parent = {}
    if participation_names:
        extra_details = frappe.get_all(
            "Participation Extra Detail",
            filters={"parent": ["in", participation_names]},
            fields=["parent", "question", "answer"],
        )

        for d in extra_details:
            parent_map = detail_by_parent.setdefault(d.parent, {})
            parent_map[scrub(d.question)] = d.answer

    res = []
    for p in participations:
        row = p
        row.update(detail_by_parent.get(p.name, {}))
            
        res.append(row)

    return columns, res
