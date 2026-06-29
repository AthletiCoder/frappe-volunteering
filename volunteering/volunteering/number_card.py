import frappe
from frappe.desk.doctype.number_card.number_card import get_result as frappe_get_result

from volunteering.volunteering.dashboard_utils import normalize_dashboard_filters


@frappe.whitelist()
def get_result(doc, filters, to_date=None):
	parsed_doc = frappe.parse_json(doc) if isinstance(doc, str) else doc
	document_type = parsed_doc.get("document_type")
	filters = normalize_dashboard_filters(filters, document_type)

	return frappe_get_result(doc, filters, to_date)
