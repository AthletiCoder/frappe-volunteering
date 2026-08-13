import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

from volunteering.volunteering.authority import BOARD_OF_DIRECTORS, user_has_board_of_directors

LEAVE_CATEGORIES = ("Normal", "Emergency")
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

	if category == "Normal":
		validate_normal_leave(doc, from_date, today, leave_days)
	elif category == "Emergency":
		validate_emergency_leave(doc, from_date, today, leave_days, settings)
	else:
		frappe.throw(_("Leave Category must be Normal or Emergency."))

	validate_director_approval(doc, leave_days)


HR_OVERRIDE_ROLES = {"HR Manager", "HR User", "System Manager"}


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
	if not leave_approver and reports_to:
		leave_approver = frappe.db.get_value("Employee", reports_to, "user_id")
	if leave_approver and doc.leave_approver != leave_approver:
		doc.leave_approver = leave_approver
		doc.leave_approver_name = frappe.db.get_value("User", leave_approver, "full_name")


def _validate_employee_field_locked(doc):
	"""Non-HR users may only create leave for themselves."""
	if _is_hr_user() or frappe.session.user == "Administrator":
		return

	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))

	if doc.employee and doc.employee != session_employee:
		frappe.throw(_("You can only create Leave Applications for yourself."))

	if not doc.employee:
		doc.employee = session_employee


def _validate_no_self_leave_approval(doc):
	"""Block changing own leave to Approved/Rejected (even with Leave Approver role)."""
	if _is_hr_user() or frappe.session.user == "Administrator":
		return

	emp_user = frappe.db.get_value("Employee", doc.employee, "user_id") if doc.employee else None
	if emp_user != frappe.session.user:
		return

	if doc.status in ("Approved", "Rejected"):
		# #region agent log
		try:
			import json
			import time

			with open(
				"/Users/varunkumar/Documents/coding/erp/erpnext/frappe-bench/.cursor/debug-4c4245.log",
				"a",
				encoding="utf-8",
			) as f:
				f.write(
					json.dumps(
						{
							"sessionId": "4c4245",
							"hypothesisId": "B",
							"location": "leave_policy.py:_validate_no_self_leave_approval",
							"message": "blocked self approval",
							"data": {"status": doc.status, "user": frappe.session.user},
							"timestamp": int(time.time() * 1000),
							"runId": "post-fix",
						}
					)
					+ "\n"
				)
		except Exception:
			pass
		# #endregion
		frappe.throw(
			_(
				"You cannot approve or reject your own Leave Application. "
				"Keep status as Open and save — your Leave Approver will decide."
			)
		)


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
	"""Emergency leave is capped by calendar consecutive days (inclusive).

	Working-day leave counts from HRMS can be shorter than the calendar span
	(weekends/holidays), but the policy is about consecutive calendar absence.
	"""
	max_days = int(settings.get("emergency_max_consecutive_days") or EMERGENCY_MAX_DAYS)
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
	if from_date < today and date_diff(today, to_date) > 2 and not _is_hr_user():
		frappe.throw(
			_(
				"Emergency leave must be regularized within {0} hours of return. "
				"Please contact HR for assistance."
			).format(EMERGENCY_REGULARIZE_HOURS)
		)


def validate_director_approval(doc, leave_days):
	if leave_days <= DIRECTOR_APPROVAL_THRESHOLD:
		return

	approver = doc.get("leave_approver")
	if not approver:
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days requires a {1} grade employee "
				"as Leave Approver."
			).format(DIRECTOR_APPROVAL_THRESHOLD, BOARD_OF_DIRECTORS)
		)

	if not user_has_director_role(approver):
		frappe.throw(
			_(
				"Leave of more than {0} consecutive days must be approved by an employee "
				"with the {1} grade."
			).format(DIRECTOR_APPROVAL_THRESHOLD, BOARD_OF_DIRECTORS)
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
	# #region agent log
	try:
		import json
		import time

		with open(
			"/Users/varunkumar/Documents/coding/erp/erpnext/frappe-bench/.cursor/debug-4c4245.log",
			"a",
			encoding="utf-8",
		) as f:
			f.write(
				json.dumps(
					{
						"sessionId": "4c4245",
						"hypothesisId": "H1",
						"location": "leave_policy.py:get_leave_form_defaults",
						"message": "defaults for leave form",
						"data": {
							"user": frappe.session.user,
							"default_leave_type": result["default_leave_type"],
							"has_lps_read": frappe.has_permission(
								"Leave Policy Settings", "read"
							),
						},
						"timestamp": int(time.time() * 1000),
						"runId": "leave-ux",
					}
				)
				+ "\n"
			)
	except Exception:
		pass
	# #endregion
	return result
