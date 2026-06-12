import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

LEAVE_CATEGORIES = ("Planned", "Emergency", "Sick")


def validate_leave_application(doc, method=None):
	if not doc.from_date:
		return

	settings = get_leave_policy_settings()
	ensure_leave_type(doc, settings)

	today = getdate(nowdate())
	from_date = getdate(doc.from_date)
	category = get_leave_category(doc)

	if category == "Planned":
		validate_planned_leave(doc, from_date, today, settings)
	elif category == "Emergency":
		validate_emergency_leave(doc, from_date, today, settings)
	elif category == "Sick":
		validate_sick_leave(doc, from_date, today)
	else:
		frappe.throw(_("Leave Category must be Planned, Emergency, or Sick."))


def ensure_leave_type(doc, settings):
	expected_leave_type = settings.get("default_leave_type") or "Privilege Leave"
	if doc.leave_type and doc.leave_type != expected_leave_type:
		frappe.throw(
			_("Paid leave must use leave type {0}. All categories share the same annual balance.").format(
				expected_leave_type
			)
		)
	if not doc.leave_type:
		doc.leave_type = expected_leave_type


def get_leave_category(doc):
	category = doc.get("leave_category") or "Planned"
	if category not in LEAVE_CATEGORIES:
		frappe.throw(_("Leave Category must be Planned, Emergency, or Sick."))
	return category


def validate_emergency_leave(doc, from_date, today, settings):
	if from_date < today:
		frappe.throw(
			_(
				"Emergency leave cannot be backdated. Apply for today or a future date, or contact HR for assistance."
			)
		)

	max_days = int(settings.get("emergency_max_consecutive_days") or 2)
	leave_days = get_application_leave_days(doc)

	if leave_days > max_days:
		frappe.throw(
			_(
				"Emergency leave cannot exceed {0} consecutive day(s). For longer absences, use Sick leave or contact HR."
			).format(max_days)
		)


def validate_sick_leave(doc, from_date, today):
	if from_date < today:
		frappe.throw(
			_("Sick leave cannot be backdated. Apply for today or a future date, or contact HR for assistance.")
		)


def validate_planned_leave(doc, from_date, today, settings):
	if from_date < today:
		frappe.throw(
			_("Backdated leave applications are not allowed. Please contact HR or your manager for assistance.")
		)

	advance_days = int(settings.get("planned_leave_advance_days") or 14)
	days_until_leave = date_diff(from_date, today)
	min_justification = int(settings.get("min_justification_length") or 20)

	if days_until_leave < advance_days:
		description = (doc.description or "").strip()
		if len(description) < min_justification:
			frappe.throw(
				_(
					"Planned leave must be applied at least {0} days in advance. "
					"Since you are applying within that window, please provide a justification "
					"of at least {1} characters in the Reason field."
				).format(advance_days, min_justification)
			)


def get_application_leave_days(doc):
	if doc.total_leave_days:
		return flt(doc.total_leave_days)

	return flt(
		get_number_of_leave_days(
			doc.employee,
			doc.leave_type,
			doc.from_date,
			doc.to_date,
			doc.half_day,
			doc.half_day_date,
		)
	)


def get_leave_policy_settings():
	if frappe.db.exists("DocType", "Leave Policy Settings"):
		return frappe.get_single("Leave Policy Settings").as_dict()

	return {
		"default_leave_type": "Privilege Leave",
		"planned_leave_advance_days": 14,
		"emergency_max_consecutive_days": 2,
		"min_justification_length": 20,
	}
