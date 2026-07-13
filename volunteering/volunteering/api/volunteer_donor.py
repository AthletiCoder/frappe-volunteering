"""Upsert Volunteer (and Customer) for donation flows."""

from __future__ import annotations

import frappe

from volunteering.volunteering.doctype.volunteer.volunteer import (
	find_volunteer_by_mobile,
	format_mobile_number,
)


def split_full_name(full_name: str) -> tuple[str, str]:
	parts = (full_name or "").strip().split(None, 1)
	if not parts:
		return "Donor", ""
	if len(parts) == 1:
		return parts[0], ""
	return parts[0], parts[1]


def upsert_volunteer_for_donation(
	*,
	full_name: str,
	mobile_number: str,
	email: str | None = None,
	pan: str | None = None,
	address: str | None = None,
) -> tuple[str, bool]:
	"""
	Find or create Volunteer by phone.
	Returns (volunteer_name, matched_existing).
	"""
	formatted_mobile = format_mobile_number(mobile_number)
	if not formatted_mobile:
		frappe.throw("Valid mobile number is required")

	existing = find_volunteer_by_mobile(formatted_mobile)
	first_name, last_name = split_full_name(full_name)

	if existing:
		volunteer = frappe.get_doc("Volunteer", existing)
		changed = False
		if first_name and volunteer.first_name != first_name:
			volunteer.first_name = first_name
			changed = True
		if last_name and volunteer.last_name != last_name:
			volunteer.last_name = last_name
			changed = True
		if email and not volunteer.email:
			if not _email_taken(email, exclude=volunteer.name):
				volunteer.email = email
				changed = True
		if pan and not volunteer.pan:
			volunteer.pan = pan.strip().upper()
			changed = True
		if address and not volunteer.address:
			volunteer.address = address
			changed = True
		if changed:
			volunteer.flags.ignore_permissions = True
			volunteer.save(ignore_permissions=True)
		return volunteer.name, True

	volunteer = frappe.new_doc("Volunteer")
	volunteer.first_name = first_name
	volunteer.last_name = last_name
	volunteer.mobile_number = formatted_mobile
	volunteer.status = "Active"
	if email and not _email_taken(email):
		volunteer.email = email
	if pan:
		volunteer.pan = pan.strip().upper()
	if address:
		volunteer.address = address
	volunteer.insert(ignore_permissions=True)
	return volunteer.name, False


def ensure_customer_for_volunteer(volunteer_name: str, full_name: str, email: str | None = None) -> str:
	"""Create or reuse a Customer linked for Payment Entry party."""
	existing = frappe.db.get_value(
		"Customer",
		{"customer_name": full_name, "mobile_no": frappe.db.get_value("Volunteer", volunteer_name, "mobile_number")},
		"name",
	)
	if existing:
		return existing

	mobile = frappe.db.get_value("Volunteer", volunteer_name, "mobile_number")
	# Prefer lookup by custom field if present, else by mobile_no
	by_mobile = frappe.db.get_value("Customer", {"mobile_no": mobile}, "name") if mobile else None
	if by_mobile:
		return by_mobile

	customer = frappe.new_doc("Customer")
	customer.customer_name = full_name
	customer.customer_type = "Individual"
	customer.customer_group = _default_customer_group()
	customer.territory = _default_territory()
	if mobile and hasattr(customer, "mobile_no"):
		customer.mobile_no = mobile
	if email and hasattr(customer, "email_id"):
		customer.email_id = email
	customer.insert(ignore_permissions=True)
	return customer.name


def _email_taken(email: str, exclude: str | None = None) -> bool:
	filters = {"email": email}
	name = frappe.db.get_value("Volunteer", filters, "name")
	if not name:
		return False
	if exclude and name == exclude:
		return False
	return True


def _default_customer_group() -> str:
	group = frappe.db.get_single_value("Selling Settings", "customer_group")
	if group:
		return group
	if frappe.db.exists("Customer Group", "Individual"):
		return "Individual"
	return frappe.db.get_value("Customer Group", {}, "name", order_by="creation asc")


def _default_territory() -> str:
	territory = frappe.db.get_single_value("Selling Settings", "territory")
	if territory:
		return territory
	if frappe.db.exists("Territory", "All Territories"):
		return "All Territories"
	return frappe.db.get_value("Territory", {}, "name", order_by="creation asc")
