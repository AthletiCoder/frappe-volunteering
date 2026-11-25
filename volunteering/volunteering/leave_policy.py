import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days
from volunteering.volunteering.hr_policy import policy_on, override_reason

from volunteering.volunteering.authority import BOARD_OF_DIRECTORS, user_has_board_of_directors

LEAVE_CATEGORIES = ("Normal", "Emergency", "Medical")
EMERGENCY_MAX_DAYS = 3
DIRECTOR_APPROVAL_THRESHOLD = 7
EMERGENCY_REGULARIZE_HOURS = 48


def validate_leave_application(doc, method=None):
	if not doc.from_date:
		return

	_ensure_leave_approver_from_reports_to(doc)
	_validate_employee_field_locked(doc)
	_validate_no_self_leave_approval(doc)

	# LWP has its own path but still follows notice / emergency rules.
	settings = get_leave_policy_settings()
	if doc.leave_type != (settings.get("leave_without_pay_type") or "Leave Without Pay"):
		ensure_leave_type(doc, settings)

	today = getdate(nowdate())
	from_date = getdate(doc.from_date)
	category = get_leave_category(doc)
	leave_days = get_application_leave_days(doc)
	policy = policy_on(from_date, revision=doc.get("sf_policy_revision"))
	exception = override_reason(doc)

	entry_changed = doc.is_new() or any(doc.has_value_changed(key) for key in ("employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date", "leave_category"))
	if not entry_changed and doc.get("hr_exception_by") and doc.get("hr_exception_reason"):
		exception = doc.hr_exception_reason  # Retain the recorded authorisation for this unchanged request.
	from volunteering.volunteering.hr_special_leave import validate_details, MATERNITY, PATERNITY
	validate_details(doc, exception)
	if category == "Normal" and not exception and entry_changed and doc.leave_type not in {MATERNITY,PATERNITY}:
		validate_normal_leave(doc, from_date, today, leave_days, policy)
	elif category == "Emergency" and not exception and entry_changed:
		validate_emergency_leave(doc, from_date, today, leave_days, settings)
	elif category not in LEAVE_CATEGORIES:
		frappe.throw(_("Leave Category must be Normal or Emergency."))

	if not exception:
		validate_director_approval(doc, leave_days, policy)
		if (doc.status == "Approved" and policy["director_approval_days"] and leave_days > policy["director_approval_days"]
			and frappe.session.user != "Administrator" and not user_has_director_role(frappe.session.user)):
			frappe.throw(_("Extended leave must be decided by its Board of Directors approver. HR can authorise an explicit exception."), frappe.PermissionError)
	from volunteering.volunteering.time_leave_portal import validate_comp_uses
	validate_comp_uses(doc)


HR_OVERRIDE_ROLES = {"HR Manager", "System Manager"}


def _is_hr_user(user=None):
	"""HR / System Manager / Administrator may override employee self-service limits."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)).intersection(HR_OVERRIDE_ROLES))


def _ensure_leave_approver_from_reports_to(doc):
	"""Prefer Employee.leave_approver, else reporting manager's user_id."""
	if not doc.employee:
		return
	leave_approver, reports_to = frappe.db.get_value(
		"Employee", doc.employee, ["leave_approver", "reports_to"]
	) or (None, None)
	if reports_to and doc.from_date and policy_on(doc.from_date, revision=doc.get("sf_policy_revision")).get("charter_enabled"):
		# The revised charter routes leave to the direct manager, even when an
		# older Employee record still names a different leave approver.
		leave_approver = frappe.db.get_value("Employee", reports_to, "user_id")
	if not leave_approver and reports_to:
		leave_approver = frappe.db.get_value("Employee", reports_to, "user_id")
	if leave_approver and doc.leave_approver != leave_approver:
		if doc.leave_approver and user_has_board_of_directors(doc.leave_approver) and not policy_on(doc.from_date, revision=doc.get("sf_policy_revision")).get("charter_enabled"):
			return
		doc.leave_approver = leave_approver
		doc.leave_approver_name = frappe.db.get_value("User", leave_approver, "full_name")


def _validate_employee_field_locked(doc):
	"""Non-HR users may only create leave for themselves."""
	if _is_hr_user():
		return

	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))

	if doc.employee and doc.employee != session_employee:
		# Reporting manager / named leave approver may save existing applications.
		if not doc.is_new():
			manager_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
			is_reports_to = (
				manager_emp
				and frappe.db.get_value("Employee", doc.employee, "reports_to") == manager_emp
			)
			is_named_approver = doc.leave_approver == frappe.session.user
			if is_reports_to or is_named_approver:
				return
		frappe.throw(_("You can only create Leave Applications for yourself."))

	if not doc.employee:
		doc.employee = session_employee


def _validate_no_self_leave_approval(doc):
	"""Block changing own leave to Approved/Rejected (even with Leave Approver role)."""
	if frappe.session.user == "Administrator":
		return

	emp_user = frappe.db.get_value("Employee", doc.employee, "user_id") if doc.employee else None
	if emp_user != frappe.session.user:
		return

	if doc.status in ("Approved", "Rejected"):
		frappe.throw(
			_(
				"You cannot approve or reject your own Leave Application. "
				"Keep status as Open and save — your Leave Approver will decide."
			)
		)


def ensure_leave_type(doc, settings):
	expected_leave_type = settings.get("default_leave_type") or "Privilege Leave"
	lwp = settings.get("leave_without_pay_type") or "Leave Without Pay"
	if doc.leave_type and doc.leave_type not in (expected_leave_type, lwp, "Compensatory Leave", "Maternity Leave", "Paternity Leave", "Optional Holiday"):
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


def validate_normal_leave(doc, from_date, today, leave_days, policy=None):
	if from_date < today:
		frappe.throw(
			_("Backdated leave is not allowed for Normal leave. Use Emergency leave or contact HR.")
		)

	days_until_leave = date_diff(from_date, today)
	import math
	policy = policy or policy_on(from_date)
	required_notice = (policy["extended_notice_days"] if leave_days > policy["short_leave_days"] and not policy.get("_legacy") else max(math.ceil(flt(leave_days)), 1))
	if days_until_leave < required_notice:
		frappe.throw(
			_(
				"This leave requires {0} days' notice; {1} days were given. Contact HR for an exception or use Emergency leave when applicable."
			).format(required_notice, days_until_leave)
		)


def validate_emergency_leave(doc, from_date, today, leave_days, settings):
	"""Emergency leave is capped by calendar consecutive days (inclusive).

	Working-day leave counts from HRMS can be shorter than the calendar span
	(weekends/holidays), but the policy is about consecutive calendar absence.
	"""
	policy = policy_on(from_date, revision=doc.get("sf_policy_revision"))
	max_days = policy["emergency_max_days"]
	to_date = getdate(doc.to_date or doc.from_date)
	calendar_days = date_diff(to_date, from_date) + 1
	if calendar_days > max_days:
		frappe.throw(
			_(
				"Emergency leave cannot exceed {0} consecutive day(s). "
				"For longer absences, apply Normal leave with notice or escalate to leadership."
			).format(max_days)
		)

	# Retroactive: must regularize within 48 hours of return (to_date + 48h).
	# HR / System Manager may backfill beyond the window on behalf of employees.
	# Approving an already-filed application must not re-apply the window.
	if from_date < today and date_diff(today, to_date) * 24 > policy["emergency_regularize_hours"]:
		if not (
			doc.is_new() or doc.has_value_changed("from_date") or doc.has_value_changed("to_date")
		):
			return
		frappe.throw(
			_(
				"Emergency leave must be regularized within {0} hours of return. "
				"Please contact HR for assistance."
			).format(policy["emergency_regularize_hours"])
		)


def validate_director_approval(doc, leave_days, policy=None):
	threshold = (policy or policy_on(doc.from_date, revision=doc.get("sf_policy_revision")))["director_approval_days"]
	if not threshold or leave_days <= threshold:
		return

	approver = doc.get("leave_approver")
	if not approver:
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days requires a {1} grade employee "
				"as Leave Approver."
			).format(threshold, BOARD_OF_DIRECTORS)
		)

	if not user_has_director_role(approver):
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days must be approved by an employee "
				"with the {1} grade."
			).format(threshold, BOARD_OF_DIRECTORS)
		)


def user_has_director_role(user):
	"""Board of Directors grade (legacy chair role still honoured while migrating)."""
	if not user:
		return False
	return user_has_board_of_directors(user)


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


@frappe.whitelist()
def get_leave_form_defaults():
	"""Safe defaults for Leave Application form (Employee need not read Leave Policy Settings)."""
	settings = get_leave_policy_settings()
	result = {
		"default_leave_type": settings.get("default_leave_type") or "Privilege Leave",
	}
	return result
