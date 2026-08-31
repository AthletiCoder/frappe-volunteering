"""Morning reminder: paid employees missing yesterday's Daily Work Log.

Phase 1 channel is email. Org toggle + hour live on Daily Work Log Settings;
each user can opt out via User.work_log_reminder_opt_in (SPA + Desk).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, formatdate, get_datetime, getdate, nowdate

from volunteering.volunteering.attendance_service import (
	get_active_employees,
	get_approved_leave,
	get_holiday_info,
	get_submitted_work_log,
	is_org_weekly_off,
)
from volunteering.volunteering.doctype.daily_work_log.daily_work_log import (
	get_daily_work_log_settings,
)
from volunteering.volunteering.employment_type import is_unpaid_employee

HOME_URL = "/volunteering/home"
WORK_LOG_NEW_URL = "/desk/daily-work-log/new"
OPT_IN_FIELD = "work_log_reminder_opt_in"


def run_morning_missing_log_reminders(force=False, reference_date=None):
	"""Hourly cron entry: send only when site hour matches settings (unless force)."""
	settings = get_daily_work_log_settings()
	if not cint(settings.get("enable_missing_log_reminder", 1)) and not force:
		return {"skipped": True, "reason": "disabled"}

	now = get_datetime()
	configured_hour = cint(settings.get("missing_log_reminder_hour") or 9)
	if not force and now.hour != configured_hour:
		return {"skipped": True, "reason": "wrong hour", "hour": now.hour, "want": configured_hour}

	log_date = getdate(reference_date or add_days(nowdate(), -1))
	if is_org_weekly_off(log_date):
		return {"skipped": True, "reason": "weekly off", "log_date": str(log_date)}

	return send_missing_log_reminders(log_date=log_date, force=force)


def send_missing_log_reminders(log_date=None, force=False, employees=None):
	"""Email each eligible paid employee who has no submitted work log for log_date.

	`employees` optionally limits the run (tests / manual targeting).
	"""
	settings = get_daily_work_log_settings()
	if not cint(settings.get("enable_missing_log_reminder", 1)) and not force:
		return {"skipped": True, "reason": "disabled"}

	log_date = getdate(log_date or add_days(nowdate(), -1))
	if is_org_weekly_off(log_date):
		return {"skipped": True, "reason": "weekly off", "log_date": str(log_date)}

	sender = (settings.get("missing_log_reminder_sender") or "").strip() or None
	sent = []
	skipped = []
	targets = list(employees) if employees is not None else get_active_employees(log_date)

	for employee in targets:
		reason = _skip_reason(employee, log_date)
		if reason:
			skipped.append({"employee": employee, "reason": reason})
			continue

		user, email = _employee_notify_target(employee)
		if not email:
			skipped.append({"employee": employee, "reason": "no email"})
			continue
		if not _user_wants_reminder(user):
			skipped.append({"employee": employee, "reason": "opted out"})
			continue
		if not force and _already_sent_today(user, log_date):
			skipped.append({"employee": employee, "reason": "already sent"})
			continue

		_send_reminder_email(
			employee=employee,
			user=user,
			email=email,
			log_date=log_date,
			sender=sender,
		)
		_mark_sent(user, log_date)
		sent.append({"employee": employee, "email": email})

	return {
		"log_date": str(log_date),
		"sent": len(sent),
		"skipped": len(skipped),
		"recipients": sent,
		"skip_detail": skipped[:50],
	}


def _skip_reason(employee, log_date):
	if is_unpaid_employee(employee):
		return "unpaid"
	if get_holiday_info(employee, log_date):
		return "holiday"
	if get_approved_leave(employee, log_date):
		return "on leave"
	if get_submitted_work_log(employee, log_date):
		return "already logged"
	return None


def _employee_notify_target(employee):
	user = frappe.db.get_value("Employee", employee, "user_id")
	email = None
	if user:
		email = frappe.db.get_value("User", user, "email")
	if not email:
		for field in ("company_email", "prefered_email", "personal_email"):
			if frappe.db.has_column("Employee", field):
				email = frappe.db.get_value("Employee", employee, field)
				if email:
					break
	return user, email


def _user_wants_reminder(user):
	if not user:
		# Employee without User: still email if we have an address (org policy).
		return True
	if not frappe.db.has_column("User", OPT_IN_FIELD):
		return True
	value = frappe.db.get_value("User", user, OPT_IN_FIELD)
	if value is None:
		return True
	return bool(cint(value))


def _cache_key(user, log_date):
	return f"work_log_reminder::{log_date}::{user or 'anon'}"


def _already_sent_today(user, log_date):
	return bool(frappe.cache.get_value(_cache_key(user, log_date)))


def _mark_sent(user, log_date):
	frappe.cache.set_value(_cache_key(user, log_date), 1, expires_in_sec=36 * 60 * 60)


def _send_reminder_email(employee, user, email, log_date, sender=None):
	day_label = formatdate(log_date, "EEEE, d MMM yyyy")
	name = frappe.db.get_value("Employee", employee, "employee_name") or employee
	subject = _("Log your work for {0}?").format(day_label)
	message = _(
		"""
		<p>Hi {name},</p>
		<p>We do not have a submitted Daily Work Log for <b>{day}</b>.</p>
		<p>Attendance for that day is finalized at noon — please add your hours if you worked.</p>
		<p>
			<a href="{log_url}">Open work log</a>
			&nbsp;·&nbsp;
			<a href="{home_url}">Home</a>
		</p>
		<p style="color:#64748b;font-size:12px;">
			You can turn off these reminders from Home (bell menu) or your User profile.
		</p>
		"""
	).format(name=name, day=day_label, log_url=WORK_LOG_NEW_URL, home_url=HOME_URL)

	frappe.sendmail(
		recipients=[email],
		sender=sender,
		subject=subject,
		message=message,
		delayed=True,
		reference_doctype="Employee",
		reference_name=employee,
	)

	if user and frappe.db.exists("DocType", "Notification Log"):
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Notification Log",
					"subject": subject,
					"email_content": message,
					"for_user": user,
					"type": "Alert",
					"document_type": "Daily Work Log",
					"link": WORK_LOG_NEW_URL,
				}
			)
			doc.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Work log reminder Notification Log failed")


@frappe.whitelist()
def send_missing_log_reminders_now(log_date=None):
	"""HR/System Manager manual send from Daily Work Log Settings."""
	frappe.only_for(("System Manager", "HR Manager", "HR User"))
	return send_missing_log_reminders(log_date=log_date, force=True)


@frappe.whitelist()
def get_notification_preferences():
	"""SPA: current user's reminder preferences."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to manage notifications."), frappe.PermissionError)
	opt_in = True
	if frappe.db.has_column("User", OPT_IN_FIELD):
		raw = frappe.db.get_value("User", user, OPT_IN_FIELD)
		opt_in = True if raw is None else bool(cint(raw))
	settings = get_daily_work_log_settings()
	return {
		"work_log_reminder_opt_in": opt_in,
		"org_enabled": bool(cint(settings.get("enable_missing_log_reminder", 1))),
		"reminder_hour": cint(settings.get("missing_log_reminder_hour") or 9),
		"browser_permission": None,
	}


@frappe.whitelist()
def set_notification_preferences(work_log_reminder_opt_in=None):
	"""SPA: update opt-in for morning missing-log emails."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to manage notifications."), frappe.PermissionError)
	if work_log_reminder_opt_in is None:
		return get_notification_preferences()
	if not frappe.db.has_column("User", OPT_IN_FIELD):
		frappe.throw(_("Notification preference field is not installed yet. Run migrate."))
	frappe.db.set_value(
		"User",
		user,
		OPT_IN_FIELD,
		1 if cint(work_log_reminder_opt_in) else 0,
		update_modified=False,
	)
	frappe.db.commit()
	return get_notification_preferences()
