import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

LEAVE_CATEGORIES = ("Normal", "Emergency")
DIRECTOR_ROLE = "Executive Board Chairperson"
EMERGENCY_MAX_DAYS = 3
DIRECTOR_APPROVAL_THRESHOLD = 7
EMERGENCY_REGULARIZE_HOURS = 48


def validate_leave_application(doc, method=None):
	if not doc.from_date:
		return

	# LWP has its own path but still follows notice / emergency rules.
	settings = get_leave_policy_settings()
	if doc.leave_type != (settings.get("leave_without_pay_type") or "Leave Without Pay"):
		ensure_leave_type(doc, settings)

	today = getdate(nowdate())
	from_date = getdate(doc.from_date)
	category = get_leave_category(doc)
	leave_days = get_application_leave_days(doc)

	if category == "Normal":
		validate_normal_leave(doc, from_date, today, leave_days)
	elif category == "Emergency":
		validate_emergency_leave(doc, from_date, today, leave_days, settings)
	else:
		frappe.throw(_("Leave Category must be Normal or Emergency."))

	validate_director_approval(doc, leave_days)


def ensure_leave_type(doc, settings):
	expected_leave_type = settings.get("default_leave_type") or "Privilege Leave"
	lwp = settings.get("leave_without_pay_type") or "Leave Without Pay"
	if doc.leave_type and doc.leave_type not in (expected_leave_type, lwp):
		frappe.throw(
			_("Paid leave must use leave type {0}. Use {1} for unpaid leave.").format(
				expected_leave_type, lwp
			)
		)
	if not doc.leave_type:
		doc.leave_type = expected_leave_type


def get_leave_category(doc):
	category = doc.get("leave_category") or "Normal"
	# Migrate legacy labels used in older docs
	if category == "Planned":
		category = "Normal"
	if category == "Sick":
		category = "Emergency"
	if category not in LEAVE_CATEGORIES:
		frappe.throw(_("Leave Category must be Normal or Emergency."))
	return category


def validate_normal_leave(doc, from_date, today, leave_days):
	if from_date < today:
		frappe.throw(
			_("Backdated leave is not allowed for Normal leave. Use Emergency leave or contact HR.")
		)

	days_until_leave = date_diff(from_date, today)
	required_notice = max(int(flt(leave_days)), 1)
	if days_until_leave < required_notice:
		frappe.throw(
			_(
				"Normal leave of {0} day(s) requires at least {0} day(s) advance notice. "
				"You applied {1} day(s) in advance. Use Emergency leave for short-notice absence."
			).format(required_notice, days_until_leave)
		)


def validate_emergency_leave(doc, from_date, today, leave_days, settings):
	max_days = int(settings.get("emergency_max_consecutive_days") or EMERGENCY_MAX_DAYS)
	if leave_days > max_days:
		frappe.throw(
			_(
				"Emergency leave cannot exceed {0} consecutive day(s). "
				"For longer absences, apply Normal leave with notice or escalate to leadership."
			).format(max_days)
		)

	# Retroactive: must regularize within 48 hours of return (to_date + 48h).
	# HR / System Manager may backfill beyond the window on behalf of employees.
	to_date = getdate(doc.to_date or doc.from_date)
	if from_date < today and date_diff(today, to_date) > 2 and not _is_hr_user():
		frappe.throw(
			_(
				"Emergency leave must be regularized within {0} hours of return. "
				"Please contact HR for assistance."
			).format(EMERGENCY_REGULARIZE_HOURS)
		)


def _is_hr_user():
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & {"HR Manager", "HR User", "System Manager"})


def validate_director_approval(doc, leave_days):
	if leave_days <= DIRECTOR_APPROVAL_THRESHOLD:
		return

	approver = doc.get("leave_approver")
	if not approver:
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days requires an Executive Board Chairperson "
				"as Leave Approver."
			).format(DIRECTOR_APPROVAL_THRESHOLD)
		)

	if not user_has_director_role(approver):
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days must be approved by a user with the "
				"Executive Board Chairperson role."
			).format(DIRECTOR_APPROVAL_THRESHOLD)
		)


def user_has_director_role(user):
	if not user:
		return False
	return DIRECTOR_ROLE in frappe.get_roles(user)


def get_application_leave_days(doc):
	if doc.total_leave_days:
		return flt(doc.total_leave_days)

	if not doc.employee or not doc.leave_type or not doc.from_date or not doc.to_date:
		return flt(date_diff(getdate(doc.to_date or doc.from_date), getdate(doc.from_date)) + 1)

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
		"leave_without_pay_type": "Leave Without Pay",
		"emergency_max_consecutive_days": EMERGENCY_MAX_DAYS,
		"director_approval_days": DIRECTOR_APPROVAL_THRESHOLD,
	}
