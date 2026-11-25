"""Dated HR policy snapshots. Publishing a rule never rewrites attendance."""
import json
import math
from contextlib import contextmanager
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, cstr, flt, getdate, nowdate, now_datetime

MANAGER_ROLES = {"HR Manager", "System Manager"}
DEFAULTS = {
	"weekly_off_day": 6, "swap_off_day": 5, "swap_notice_weekday": 3,
	"work_log_days": 2, "full_day_hours": 6, "comp_hours": 6,
	"comp_valid_months": 1, "comp_half_day_enabled": 0,
	"monthly_leave": 2.5, "carry_forward_days": 15, "leave_year_start_month": 1,
	"short_leave_days": 3, "extended_notice_days": 14,
	"emergency_max_days": 3, "emergency_regularize_hours": 48,
	"director_approval_days": 7, "allow_negative_paid_leave": 1,
	"apply_to_unpaid": 0,
	"attendance_based_payroll": 1,
	"half_day_hours": 0, "calendar_day_payroll": 0,
	"medical_certificate_days": 2, "medical_notice_days": 0,
	"maternity_weeks": 26, "paternity_days": 5, "paternity_window_months": 3,
	"optional_holidays": 2, "charter_enabled": 0,
	"pf_employee_rate": 12, "pf_employer_rate": 12, "pf_wage_ceiling": 25000,
	"pt_male_lower": 7500, "pt_male_upper": 10000, "pt_female_exempt": 25000,
	"pt_middle_rate": 175, "pt_regular_rate": 200, "pt_february_rate": 300,
}
LABELS = {
	"weekly_off_day": "Weekly off", "swap_off_day": "Alternative weekly off",
	"swap_notice_weekday": "Swap request deadline", "work_log_days": "Days allowed to log work",
	"full_day_hours": "Hours for a full working day", "comp_hours": "Hours for a compensatory day",
	"comp_valid_months": "Compensatory leave validity (months)", "comp_half_day_enabled": "Allow half-day compensatory credit automatically",
	"monthly_leave": "Paid leave earned each month", "carry_forward_days": "Maximum carry-forward days",
	"leave_year_start_month": "First month of leave year", "short_leave_days": "Short leave limit (days)",
	"extended_notice_days": "Notice for extended leave (days)", "emergency_max_days": "Emergency leave limit (days)",
	"emergency_regularize_hours": "Emergency regularisation window (hours)",
	"director_approval_days": "Director approval above this many days (0 disables)",
	"allow_negative_paid_leave": "Allow paid leave in advance of accrual", "apply_to_unpaid": "Apply automatic attendance and leave to unsalaried staff",
	"attendance_based_payroll": "Use attendance for salary deductions (absent and half days)",
	"half_day_hours": "Minimum hours for a half working day", "calendar_day_payroll": "Divide monthly salary by calendar days",
	"medical_certificate_days": "Medical certificate required after consecutive days", "medical_notice_days": "Days allowed to inform manager of sudden illness",
	"maternity_weeks": "Maternity entitlement (weeks)", "paternity_days": "Paternity entitlement (working days)", "paternity_window_months": "Paternity leave window after childbirth (months)",
	"optional_holidays": "Optional holidays per year", "charter_enabled": "Enable December 2026 team charter",
	"pf_employee_rate": "Employee PF rate (%)", "pf_employer_rate": "Employer PF rate (%)", "pf_wage_ceiling": "Company PF wage ceiling (INR)",
	"pt_male_lower": "Maharashtra PT lower salary threshold", "pt_male_upper": "Maharashtra PT upper salary threshold", "pt_female_exempt": "Maharashtra PT female exemption threshold",
	"pt_middle_rate": "PT middle band (INR)", "pt_regular_rate": "PT monthly upper band (INR)", "pt_february_rate": "PT February upper band (INR)",
}


def is_policy_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(MANAGER_ROLES.intersection(frappe.get_roles(user)))


def require_policy_manager():
	if not is_policy_manager():
		frappe.throw(_("Only HR Managers or System Managers can change HR policy or authorise exceptions."), frappe.PermissionError)


@contextmanager
def hr_leave_validation_access():
	"""Allow HRMS leave maths despite HR's automatic own-Employee restriction.

	Only the request-local permission cache is scoped; Redis, saved User
	Permissions, the acting user and other restrictions (e.g. Company) stay intact.
	The Leave Application controller uses this solely while validating leave.
	"""
	if not is_policy_manager():
		yield
		return
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	user = frappe.session.user
	permissions = get_user_permissions(user)
	if "Employee" not in permissions:
		yield
		return
	key = frappe.cache.make_key("user_permissions")
	bucket = frappe.local.cache.setdefault(key, {})
	had_original = user in bucket
	original = bucket.get(user)
	bucket[user] = {kind: values for kind, values in permissions.items() if kind != "Employee"}
	try:
		yield
	finally:
		if had_original:
			bucket[user] = original
		else:
			bucket.pop(user, None)


def reason_text(value):
	value = cstr(value).strip()
	if not 10 <= len(value) <= 2000:
		frappe.throw(_("Explain the change or exception in 10 to 2000 characters."))
	return value


def clean_policy(raw):
	if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
		frappe.throw(_("Unsupported HR policy fields."))
	values = {**DEFAULTS, **raw}
	limits = {"weekly_off_day": (0, 6), "swap_off_day": (0, 6), "swap_notice_weekday": (0, 6),
		"work_log_days": (0, 31), "full_day_hours": (0.25, 24), "comp_hours": (0.25, 24),
		"comp_valid_months": (1, 12), "comp_half_day_enabled": (0, 1), "monthly_leave": (0, 10),
		"carry_forward_days": (0, 120), "leave_year_start_month": (1, 12), "short_leave_days": (1, 30),
		"extended_notice_days": (0, 90), "emergency_max_days": (1, 31),
		"emergency_regularize_hours": (0, 720), "director_approval_days": (0, 365),
		"allow_negative_paid_leave": (0, 1), "apply_to_unpaid": (0, 1), "attendance_based_payroll": (0, 1)}
	limits.update({"half_day_hours": (0, 24), "calendar_day_payroll": (0, 1), "medical_certificate_days": (0, 30), "medical_notice_days": (0, 14),
		"maternity_weeks": (26, 52), "paternity_days": (1, 30), "paternity_window_months": (1, 12), "optional_holidays": (0, 12), "charter_enabled": (0, 1),
		"pf_employee_rate": (0, 100), "pf_employer_rate": (0, 100), "pf_wage_ceiling": (0, 1000000),
		"pt_male_lower": (0, 1000000), "pt_male_upper": (0, 1000000), "pt_female_exempt": (0, 1000000),
		"pt_middle_rate": (0, 100000), "pt_regular_rate": (0, 100000), "pt_february_rate": (0, 100000)})
	for key, (minimum, maximum) in limits.items():
		try: number = float(values[key])
		except (ValueError, TypeError): frappe.throw(_("Enter a number for {0}.").format(LABELS[key]))
		if not math.isfinite(number) or not minimum <= number <= maximum:
			frappe.throw(_("{0} must be between {1} and {2}.").format(LABELS[key], minimum, maximum))
		if key not in {"full_day_hours", "half_day_hours", "comp_hours", "monthly_leave", "carry_forward_days", "pf_employee_rate", "pf_employer_rate"} and number != int(number):
			frappe.throw(_("{0} must be a whole number.").format(LABELS[key]))
		values[key] = number if key in {"full_day_hours", "half_day_hours", "comp_hours", "monthly_leave", "carry_forward_days", "pf_employee_rate", "pf_employer_rate"} else int(number)
	if values["half_day_hours"] >= values["full_day_hours"]: frappe.throw(_("Half-day hours must be below full-day hours."))
	if values["pt_male_lower"] > values["pt_male_upper"]: frappe.throw(_("The PT lower threshold must not exceed the upper threshold."))
	if values["weekly_off_day"] == values["swap_off_day"]:
		frappe.throw(_("The alternative weekly off must be a different day."))
	if any(values[key] * 4 != round(values[key] * 4) for key in ("monthly_leave", "carry_forward_days")):
		frappe.throw(_("Monthly leave and carry-forward must use quarter-day increments, for example 2.5 or 2.75."))
	return values


def legacy_policy():
	values = {**DEFAULTS, "weekly_off_day": 2, "carry_forward_days": 0,
		"leave_year_start_month": 4, "extended_notice_days": 0, "attendance_based_payroll": 0, "_legacy": True}
	if frappe.db.exists("DocType", "Daily Work Log Settings"):
		settings = frappe.get_single("Daily Work Log Settings")
		values["work_log_days"] = cint(settings.backdate_limit_days if settings.backdate_limit_days is not None else 2)
		values["full_day_hours"] = flt(settings.present_hours_threshold or 6)
	return values


def _clear_policy_cache():
	frappe.local.sf_hr_policies = None


def policy_on(day=None, revision=None):
	day = getdate(day or nowdate())
	if frappe.db.exists("DocType", "HR Policy Revision"):
		rows = getattr(frappe.local, "sf_hr_policies", None)
		if rows is None:
			rows = frappe.get_all("HR Policy Revision", fields=["name", "effective_from", "settings"], order_by="effective_from desc, creation desc", limit_page_length=0)
			frappe.local.sf_hr_policies = rows
			# A worker or CLI command can continue after committing or rolling back.
			# Never retain a revision that belonged to the previous transaction.
			frappe.db.after_commit.add(_clear_policy_cache)
			frappe.db.after_rollback.add(_clear_policy_cache)
		row = next((row for row in rows if row.name == revision), None) if revision else next((row for row in rows if getdate(row.effective_from) <= day), None)
		if row:
			return {**DEFAULTS, **frappe.parse_json(row.settings), "_revision": row.name, "_effective_from": str(row.effective_from)}
	return legacy_policy()


def leave_year(day=None, policy=None):
	day = getdate(day or nowdate()); month = int((policy or policy_on(day))["leave_year_start_month"])
	start = date(day.year if day.month >= month else day.year - 1, month, 1)
	return start, getdate(add_days(add_months(start, 12), -1))


def deadline_for_log(day, policy=None):
	# Two calendar days after a workday means its date plus two, through 23:59.
	return getdate(add_days(day, int((policy or policy_on(day))["work_log_days"]) + 1))


def applies_to_employee(employee, day=None):
	from volunteering.volunteering.employment_type import is_unpaid_employee
	return bool(policy_on(day)["apply_to_unpaid"] or not is_unpaid_employee(employee))


def override_reason(doc):
	value = cstr(doc.flags.get("hr_exception_reason")).strip()
	if not value and doc.get("hr_exception_reason") and (doc.is_new() or doc.has_value_changed("hr_exception_reason")):
		value = doc.hr_exception_reason
	if not value:
		if any(doc.get(key) and (doc.is_new() or doc.has_value_changed(key)) for key in ("hr_exception_by", "hr_exception_on")):
			frappe.throw(_("HR exception identity and time are assigned by the server."), frappe.PermissionError)
		return ""
	require_policy_manager()
	value = reason_text(value)
	doc.hr_exception_reason = value
	doc.hr_exception_by = frappe.session.user
	doc.hr_exception_on = now_datetime()
	return value


def audit_exception(doc, method=None):
	if doc.get("hr_exception_reason") and (doc.is_new() or doc.has_value_changed("hr_exception_on")):
		doc.add_comment("Info", _("HR exception authorised by {0}: {1}").format(
			frappe.utils.escape_html(doc.get("hr_exception_by") or frappe.session.user),
			frappe.utils.escape_html(doc.hr_exception_reason)))


def ensure_policy_defaults():
	if not frappe.db.exists("DocType", "HR Policy Revision"): return
	if not frappe.db.count("HR Policy Revision"):
		_create_revision(DEFAULTS, min(getdate(nowdate()), date(2026, 11, 30)), "Initial team policy: calendar-year leave, Sunday off and HR-authorised exceptions.")
	ensure_december_charter()


def ensure_december_charter():
	key = "team-charter-2026-12-01"
	if not frappe.get_meta("HR Policy Revision").has_field("policy_key") or frappe.db.exists("HR Policy Revision", {"policy_key": key}): return
	values = {k: policy_on("2026-12-01")[k] for k in DEFAULTS}
	values.update(work_log_days=4, comp_valid_months=2, half_day_hours=3, director_approval_days=0, calendar_day_payroll=1, charter_enabled=1)
	doc = _create_revision(values, "2026-12-01", "Team policy charter effective 1 December 2026: four-day logging, two-month comp-off, manager leave approvals and calendar-day payroll.")
	doc.db_set("policy_key", key)


def _create_revision(values, effective_from, reason):
	doc = frappe.get_doc({"doctype": "HR Policy Revision", "effective_from": effective_from,
		"settings": json.dumps(values), "reason": reason, "published_by": frappe.session.user, "published_on": now_datetime()})
	doc.flags.policy_publication = True
	doc.insert(ignore_permissions=True)
	frappe.local.sf_hr_policies = None
	return doc


@frappe.whitelist(methods=["POST"])
def get_hr_policy_workspace():
	require_policy_manager()
	return {"policy": {key: policy_on()[key] for key in DEFAULTS}, "revision": policy_on().get("_revision"),
		"publication_revision": frappe.db.get_value("HR Policy Revision", {}, "name", order_by="creation desc"),
		"labels": LABELS, "today": nowdate(), "history": frappe.get_all("HR Policy Revision",
			fields=["name", "effective_from", "published_by", "published_on", "reason", "settings"],
			order_by="effective_from desc, creation desc", limit=100)}


@frappe.whitelist(methods=["POST"])
def publish_hr_policy(values, effective_from, reason, expected_revision=None, expected_publication_revision=None):
	require_policy_manager()
	values = clean_policy(frappe.parse_json(values)); reason = reason_text(reason)
	effective_from = getdate(effective_from)
	if effective_from < getdate(nowdate()):
		frappe.throw(_("Publish policy for today or a future date. Correct historical records through a reasoned HR exception."))
	# Stable row lock for every policy publisher; no mid-request commits.
	frappe.db.get_value("Company", "Sevamrita Foundation", "name", for_update=True)
	if expected_publication_revision is not None and cstr(expected_publication_revision) != cstr(frappe.db.get_value("HR Policy Revision", {}, "name", order_by="creation desc")):
		frappe.throw(_("A policy revision was published while you were editing. Refresh before publishing."))
	if cstr(expected_revision) != cstr(policy_on().get("_revision")):
		frappe.throw(_("The active policy changed. Refresh before publishing."))
	if any(values[key] != policy_on(effective_from)[key] for key in ("weekly_off_day", "swap_off_day", "leave_year_start_month")):
		if frappe.db.exists("Leave Application", {"status": ["in", ["Open", "Approved"]], "docstatus": ["<", 2], "to_date": [">=", effective_from]}):
			frappe.throw(_("Resolve open or approved future leave before changing the working week or leave year. This protects already agreed leave counts."))
	_create_revision(values, effective_from, reason)
	if effective_from <= getdate(nowdate()):
		from volunteering.volunteering.hr_leave_balances import sync_leave_masters
		sync_leave_masters()
	frappe.enqueue("volunteering.volunteering.employee_calendars.sync_all_calendars", enqueue_after_commit=True)
	return get_hr_policy_workspace()
