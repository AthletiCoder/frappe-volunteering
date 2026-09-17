# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee-visible, Accounts Manager-controlled company office addresses."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

SEVAMRITA_COMPANY = "Sevamrita Foundation"
MANAGER_ROLE = "Accounts Manager"
ALLOWED_ADDRESS_TYPES = {
	"Billing",
	"Shipping",
	"Office",
	"Plant",
	"Postal",
	"Shop",
	"Subsidiary",
	"Warehouse",
	"Other",
}
def can_manage_office_addresses(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or MANAGER_ROLE in frappe.get_roles(user)


def _can_view_office_addresses(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	if can_manage_office_addresses(user):
		return True
	return bool(frappe.db.exists("Employee", {"user_id": user, "status": "Active"}))


def _require_viewer():
	if not _can_view_office_addresses():
		frappe.throw(_("Only employees may view office addresses."), frappe.PermissionError)


def _require_manager():
	if not can_manage_office_addresses():
		frappe.throw(
			_("Only an Accounts Manager or Administrator may add, edit or delete office addresses."),
			frappe.PermissionError,
		)


def _company():
	if frappe.db.exists("Company", SEVAMRITA_COMPANY):
		return SEVAMRITA_COMPANY
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	return company or frappe.db.get_value("Company", {}, "name")


@frappe.whitelist(methods=["POST"])
def get_office_address_workspace():
	_require_viewer()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def save_office_address(details, name=None, expected_modified=None):
	_require_manager()
	company = _company()
	if not company:
		frappe.throw(_("Set up Sevamrita Foundation before adding an office address."))
	values = _normalise(details)
	if name:
		doc = _office_address(name, company)
		_check_modified(doc, expected_modified)
		for field, value in values.items():
			doc.set(field, value)
	else:
		doc = frappe.new_doc("Address")
		for field, value in values.items():
			doc.set(field, value)
		doc.append("links", {"link_doctype": "Company", "link_name": company})
		doc.is_your_company_address = 1
	doc.flags.ignore_permissions = True
	doc.save()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def delete_office_address(name, expected_modified=None):
	_require_manager()
	doc = _office_address(name, _company())
	_check_modified(doc, expected_modified)
	frappe.delete_doc("Address", doc.name, ignore_permissions=True)
	return _workspace()


def validate_office_address_mutation(doc, method=None):
	"""Protect company-linked Address writes even through Desk, imports or direct APIs."""
	if not _was_or_is_company_address(doc):
		return
	if can_manage_office_addresses():
		return
	frappe.throw(
		_("Only an Accounts Manager or Administrator may add, edit or delete office addresses."),
		frappe.PermissionError,
	)


def _was_or_is_company_address(doc):
	if cint(doc.get("is_your_company_address")):
		return True
	if any(row.link_doctype == "Company" for row in (doc.get("links") or [])):
		return True
	if doc.is_new() or not doc.name:
		return False
	return bool(
		frappe.db.exists(
			"Dynamic Link",
			{
				"parenttype": "Address",
				"parent": doc.name,
				"link_doctype": "Company",
			},
		)
	)


def _workspace():
	company = _company()
	return {
		"company": company,
		"can_manage": can_manage_office_addresses(),
		"addresses": _address_rows(company, include_disabled=can_manage_office_addresses()),
		"address_types": sorted(ALLOWED_ADDRESS_TYPES),
	}


def invoice_address_choices(company):
	"""Return active company addresses in the shape used by the invoice form."""
	choices = []
	for row in _address_rows(company):
		lines = [row.address_line1, row.address_line2, row.city, row.county]
		locality = ", ".join(
			str(value).strip() for value in (row.city, row.state, row.pincode) if value
		)
		choices.append(
			{
				"name": row.name,
				"label": f"{row.address_title} - {locality}",
				"address_title": row.address_title,
				"address_type": row.address_type,
				"is_primary_address": cint(row.is_primary_address),
				"is_shipping_address": cint(row.is_shipping_address),
				"party": {
					"address": ", ".join(str(value).strip() for value in lines if value),
					"state": row.state or "",
					"pin_code": row.pincode or "",
				},
			}
		)
	return choices


def _address_rows(company, include_disabled=False):
	if not company:
		return []
	disabled_filter = "" if include_disabled else "AND IFNULL(address.disabled, 0) = 0"
	return frappe.db.sql(
		f"""
		SELECT DISTINCT
			address.name, address.modified, address.address_title, address.address_type,
			address.address_line1, address.address_line2, address.city, address.county,
			address.state, address.country, address.pincode, address.email_id,
			address.phone, address.is_primary_address, address.is_shipping_address,
			address.disabled
		FROM `tabAddress` address
		INNER JOIN `tabDynamic Link` link
			ON link.parent = address.name AND link.parenttype = 'Address'
		WHERE link.link_doctype = 'Company' AND link.link_name = %s
			{disabled_filter}
		ORDER BY address.is_primary_address DESC, address.disabled ASC,
			address.address_title ASC, address.name ASC
		""",
		(company,),
		as_dict=True,
	)


def _office_address(name, company):
	if not name or not company:
		frappe.throw(_("Office address not found."), frappe.DoesNotExistError)
	linked = frappe.db.exists(
		"Dynamic Link",
		{
			"parenttype": "Address",
			"parent": name,
			"link_doctype": "Company",
			"link_name": company,
		},
	)
	if not linked:
		frappe.throw(_("Office address not found."), frappe.DoesNotExistError)
	return frappe.get_doc("Address", name)


def _normalise(details):
	raw = frappe.parse_json(details) if isinstance(details, str) else details
	if not isinstance(raw, dict):
		frappe.throw(_("Address details must be a valid object."))
	address_type = _required(raw, "address_type", _("Address type"), 40)
	if address_type not in ALLOWED_ADDRESS_TYPES:
		frappe.throw(_("Choose a valid office address type."))
	return {
		"address_title": _required(raw, "address_title", _("Address title"), 160),
		"address_type": address_type,
		"address_line1": _required(raw, "address_line1", _("Address line 1"), 240),
		"address_line2": _text(raw.get("address_line2"), 240),
		"city": _required(raw, "city", _("City/Town"), 140),
		"county": _text(raw.get("county"), 140),
		"state": _text(raw.get("state"), 140),
		"country": _required(raw, "country", _("Country"), 140),
		"pincode": _text(raw.get("pincode"), 20),
		"email_id": _text(raw.get("email_id"), 140),
		"phone": _text(raw.get("phone"), 40),
		"is_primary_address": cint(bool(raw.get("is_primary_address"))),
		"is_shipping_address": cint(bool(raw.get("is_shipping_address"))),
		"disabled": cint(bool(raw.get("disabled"))),
	}


def _required(raw, key, label, maximum):
	value = _text(raw.get(key), maximum)
	if not value:
		frappe.throw(_("{0} is required.").format(label))
	return value


def _text(value, maximum):
	value = str(value or "").strip()
	if len(value) > maximum:
		frappe.throw(_("Value is too long (maximum {0} characters).").format(maximum))
	return value


def _check_modified(doc, expected_modified):
	if expected_modified and str(doc.modified) != str(expected_modified):
		frappe.throw(_("This address changed after you opened it. Refresh and try again."))
