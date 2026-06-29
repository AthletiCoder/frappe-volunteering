import frappe


def normalize_dashboard_filters(filters, document_type):
	"""Convert workspace filter-group dicts to frappe filter lists."""
	if filters is None:
		return []

	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	if not filters:
		return []

	if isinstance(filters, list):
		return filters

	if isinstance(filters, dict):
		if not document_type:
			return []

		normalized = []
		for fieldname, value in filters.items():
			if value in (None, ""):
				continue
			normalized.append([document_type, fieldname, "=", value])
		return normalized

	return []
