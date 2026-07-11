"""Reconcile stuck Pending donations against Cashfree Get Order."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

from volunteering.volunteering.api.donations import mark_donation_from_order_status


def reconcile_pending_donations(minutes_old: int = 15, limit: int = 50):
	"""Find Pending/Initiated donations older than N minutes and refresh from Cashfree."""
	cutoff = add_to_date(now_datetime(), minutes=-minutes_old)
	rows = frappe.get_all(
		"Donation",
		filters={
			"status": ["in", ["Initiated", "Pending"]],
			"cashfree_order_id": ["is", "set"],
			"modified": ["<", cutoff],
		},
		fields=["name"],
		order_by="modified asc",
		limit=limit,
	)

	results = []
	for row in rows:
		try:
			status = mark_donation_from_order_status(row.name)
			results.append({"name": row.name, "status": status})
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), f"Reconcile failed for {row.name}")
			results.append({"name": row.name, "status": "error"})

	return results
