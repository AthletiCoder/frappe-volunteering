import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


ATTENDANCE_STATUS_OPTIONS = "\nPresent\nAbsent\nOn Leave\nHalf Day\nWork From Home\nHoliday"


def execute():
	ensure_holiday_status_option()


def ensure_holiday_status_option():
	existing = frappe.db.exists(
		"Property Setter",
		{"doc_type": "Attendance", "field_name": "status", "property": "options"},
	)
	if existing:
		frappe.db.set_value("Property Setter", existing, "value", ATTENDANCE_STATUS_OPTIONS)
	else:
		make_property_setter(
			"Attendance",
			"status",
			"options",
			ATTENDANCE_STATUS_OPTIONS,
			"Text",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Attendance")
