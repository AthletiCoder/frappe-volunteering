"""Employee/manager/HR time and leave workflows shared by Home and Android."""
import hashlib
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, cstr, flt, getdate, nowdate, now_datetime

from volunteering.volunteering.hr_policy import (
	DEFAULTS, applies_to_employee, is_policy_manager, leave_year, override_reason,
	policy_on, reason_text, require_policy_manager,
)
from volunteering.volunteering.hr_leave_balances import (
	PAID, COMP, LWP, ensure_current_balance, ensure_allocation, lock_employee,
	paid_balance, post_leave, require_unprocessed_salary,
)

TYPES = {"Weekly Off Swap", "Compensatory Credit", "WFH", "Attendance Correction"}


def access():
	if frappe.session.user == "Guest": frappe.throw(_("Sign in to open Time and leave."), frappe.PermissionError)
	emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "employee_name"], as_dict=True)
	hr = is_policy_manager()
	if not emp and not hr: frappe.throw(_("An active employee record is required."), frappe.PermissionError)
	people = frappe.get_all("Employee", filters={"status": "Active"} if hr else {"reports_to": emp.name, "status": "Active"},
		fields=["name", "employee_name", "employment_type"], order_by="employee_name", limit_page_length=0)
	if not hr:
		assigned = set(frappe.get_all("Leave Application", filters={"leave_approver": frappe.session.user, "docstatus": ["<", 2]}, pluck="employee"))
		assigned.update(frappe.get_all("Staff Time Request", filters={"approver": frappe.session.user}, pluck="employee"))
		known = {row.name for row in people} | {emp.name}
		if assigned - known:
			people.extend(frappe.get_all("Employee", filters={"name": ["in", list(assigned-known)], "status": "Active"}, fields=["name", "employee_name", "employment_type"]))
	return {"employee": emp, "can_override": hr, "can_review": hr or bool(people), "people": people}


def _employee(value=None):
	data = access(); own = (data["employee"] or {}).get("name")
	target = value or own
	if not target or (target != own and not data["can_override"]):
		frappe.throw(_("Only HR Managers can submit on another employee's behalf."), frappe.PermissionError)
	if frappe.db.get_value("Employee", target, "status") != "Active": frappe.throw(_("Choose an active employee."))
	if not applies_to_employee(target): frappe.throw(_("Automatic leave and attendance policy applies to salaried employees only."))
	return target


def _can_review(employee, approver=None, needs_hr=False):
	if frappe.db.get_value("Employee", employee, "user_id") == frappe.session.user and frappe.session.user != "Administrator":
		return False
	if is_policy_manager(): return True
	if needs_hr: return False
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	return bool((approver and approver == frappe.session.user) or
		(manager and frappe.db.get_value("Employee", manager, "user_id") == frappe.session.user))


def _approver(employee, hr_only=False):
	if not hr_only:
		manager = frappe.db.get_value("Employee", employee, "reports_to")
		user = frappe.db.get_value("Employee", manager, "user_id") if manager else None
		if user and frappe.db.get_value("User", user, "enabled"): return user
	own = frappe.db.get_value("Employee", employee, "user_id")
	for user in frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent"):
		if user != own and frappe.db.get_value("User", user, "enabled"): return user
	return "Administrator"


def _key(employee, key):
	if not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", cstr(key)): frappe.throw(_("A valid request reference is required."))
	return hashlib.sha256(f"{employee}:{key}".encode()).hexdigest()


def _normal_row(doc):
	leave = doc.doctype == "Leave Application"
	return {"name": doc.name, "doctype": doc.doctype, "employee": doc.employee,
		"employee_name": doc.employee_name, "type": (doc.leave_type if leave else doc.request_type),
		"from_date": str(doc.from_date), "to_date": str(doc.to_date), "status": doc.status,
		"reason": doc.description if leave else doc.reason, "modified": str(doc.modified),
		"days": doc.total_leave_days if leave else doc.credit_days, "valid_until": doc.get("valid_until"),
		"approver": doc.get("leave_approver") if leave else doc.approver,
		"half_day": doc.get("half_day"), "half_day_date": doc.get("half_day_date"),
		"can_decide": doc.status == "Open" and _can_decide_doc(doc),
		"can_cancel": doc.status == "Open" and (is_policy_manager() or frappe.db.get_value("Employee", doc.employee, "user_id") == frappe.session.user),
		"can_reverse": doc.status == "Approved" and is_policy_manager(),
		"hr_exception_reason": doc.get("hr_exception_reason"), "decision_reason": doc.get("decision_reason"),
		"decision_by": doc.get("decision_by"), "decision_on": doc.get("decision_on"), "requires_hr": bool(doc.get("requires_hr")),
		"requested_status": doc.get("requested_status"), "certificate_url": doc.get("sf_medical_certificate"),
        "manager_notified_on":doc.get("sf_manager_notified_on"),"childbirth_date":doc.get("sf_childbirth_date"),"parental_case":doc.get("sf_parental_case"),
        "eligibility_verified_by":doc.get("sf_eligibility_verified_by"), "eligibility_reason":doc.get("sf_eligibility_reason"),
        "can_verify_eligibility":bool(leave and doc.leave_type in {"Maternity Leave","Paternity Leave"} and doc.status=="Open" and is_policy_manager()
            and frappe.db.get_value("Employee",doc.employee,"user_id")!=frappe.session.user),
        "can_attach_certificate":bool(leave and doc.status=="Open" and (is_policy_manager() or frappe.db.get_value("Employee",doc.employee,"user_id")==frappe.session.user))}


def _can_decide_doc(doc):
	if not _can_review(doc.employee, doc.get("leave_approver") if doc.doctype == "Leave Application" else doc.approver, doc.get("requires_hr")): return False
	if doc.doctype == "Leave Application" and not is_policy_manager():
		policy = policy_on(doc.from_date, revision=doc.get("sf_policy_revision"))
		if policy["director_approval_days"] and doc.total_leave_days > policy["director_approval_days"] and not doc.get("hr_exception_by"):
			from volunteering.volunteering.authority import user_has_board_of_directors
			return doc.leave_approver == frappe.session.user and user_has_board_of_directors(frappe.session.user)
	return True


@frappe.whitelist(methods=["POST"])
def get_time_workspace(view="mine", employee=""):
	from volunteering.volunteering.expense_claim_requests import _retry_snapshot_conflict
	return _retry_snapshot_conflict(lambda: _time_workspace(view, employee))


def _time_workspace(view="mine", employee=""):
	data = access(); own = (data["employee"] or {}).get("name")
	if view not in {"mine", "team"}: frappe.throw(_("Choose My requests or Team review."))
	if view == "team" and not data["can_review"]: frappe.throw(_("You cannot review this team."), frappe.PermissionError)
	allowed = [row.name for row in data["people"]]
	if employee and employee != own and employee not in allowed: frappe.throw(_("You cannot access these requests."), frappe.PermissionError)
	people = ([employee] if employee else allowed) if view == "team" else [own or "__none__"]
	rows = []
	for doctype in ("Leave Application", "Staff Time Request"):
		for name in frappe.get_all(doctype, filters={"employee": ["in", people], "docstatus": ["<", 2]}, pluck="name", order_by="creation desc", limit=150):
			doc = frappe.get_doc(doctype, name)
			if view == "team" and not data["can_override"] and not _can_review(doc.employee, doc.get("leave_approver") if doctype == "Leave Application" else doc.approver, doc.get("requires_hr")): continue
			rows.append(_normal_row(doc))
	policy = policy_on(); personal = bool(own and applies_to_employee(own))
	if personal: ensure_current_balance(own)
	credits = _credits(own) if personal else []
	return {**data, "view": view, "requests": sorted(rows, key=lambda row: row["modified"], reverse=True),
		"request_types": [PAID, COMP, LWP, "Maternity Leave", "Paternity Leave", "Optional Holiday", *sorted(TYPES)], "special_effective_from":"2026-12-01",
		"policy": {key: policy[key] for key in DEFAULTS}, "policy_effective_from": policy.get("_effective_from"),
		"eligible": personal, "today": nowdate(), "paid_balance": paid_balance(own) if personal else 0,
		"comp_balance": flt(sum(row["available"] for row in credits)), "credits": credits,
		"postings": frappe.get_all("HR Leave Posting", filters={"employee": own or "__none__"},
			fields=["name", "posting_date", "days", "leave_type", "reason", "source", "adjustment"], order_by="creation desc", limit=50),
		"leave_year": [str(day) for day in leave_year()], "legacy_allocation": bool(personal and not (frappe.db.get_value("Leave Allocation",
			{"employee": own, "leave_type": PAID, "docstatus": 1, "from_date": ["<=", nowdate()], "to_date": [">=", nowdate()]}, "sf_managed_policy")))}


def leave_units(employee, start, end, half_day=False, half_day_date=None, include_holidays=False):
	from volunteering.volunteering.employee_calendars import holiday_on
	start, end = getdate(start), getdate(end)
	if end < start or (end-start).days > 366: frappe.throw(_("Choose a date range of at most one year."))
	return [(start + timedelta(days=offset), 0.5 if half_day and getdate(half_day_date or start) == start + timedelta(days=offset) else 1)
		for offset in range((end-start).days+1) if include_holidays or not holiday_on(employee, start + timedelta(days=offset))]


@frappe.whitelist(methods=["POST"])
def submit_time_request(details, request_key):
	from volunteering.volunteering.expense_claim_requests import _retry_snapshot_conflict
	return _retry_snapshot_conflict(lambda: _submit_request(details, request_key))


def _submit_request(details, request_key):
	raw = frappe.parse_json(details)
	if not isinstance(raw, dict): frappe.throw(_("Enter request details."))
	employee = _employee(raw.get("employee")); lock_employee(employee)
	key = _key(employee, request_key)
	fingerprint = hashlib.sha256(frappe.as_json(raw).encode()).hexdigest()
	existing = frappe.db.get_value("Staff Time Request", {"request_key": key}, ["name", "request_fingerprint"], as_dict=True, for_update=True)
	if existing:
		if existing.request_fingerprint != fingerprint: frappe.throw(_("This request reference was used for different details."))
		return _normal_row(frappe.get_doc("Staff Time Request", existing.name))
	leave = frappe.db.get_value("Leave Application", {"employee": employee, "sf_request_key": key}, ["name", "sf_request_fingerprint"], as_dict=True, for_update=True)
	if leave:
		if leave.sf_request_fingerprint != fingerprint: frappe.throw(_("This request reference was used for different details."))
		return _normal_row(frappe.get_doc("Leave Application", leave.name))
	reason = cstr(raw.get("reason")).strip()
	if not 10 <= len(reason) <= 2000: frappe.throw(_("Describe your request in 10 to 2000 characters."))
	if not raw.get("from_date"): frappe.throw(_("Choose a request date."))
	start, end = getdate(raw.get("from_date")), getdate(raw.get("to_date") or raw.get("from_date"))
	type = raw.get("type")
	# A swap stores the work Sunday first and the replacement Saturday second.
	# These are a pair of dates, rather than the ends of an absence range.
	if abs((end-start).days)>366 or (end<start and type != "Weekly Off Swap"):
		frappe.throw(_("Choose a date range of at most one year."))
	policy = policy_on(start)
	exception = reason_text(raw["hr_exception_reason"]) if raw.get("hr_exception_reason") else ""
	if exception: require_policy_manager()
	if employee != (access()["employee"] or {}).get("name") and not exception:
		frappe.throw(_("Explain the HR exception before submitting for another employee."))
	from volunteering.volunteering.hr_special_leave import SPECIAL, prepare_special, bind_certificate
	if type in {PAID, COMP, LWP} | SPECIAL:
		from volunteering.volunteering.employee_calendars import sync_employee_calendar
		for year in range(start.year, end.year+1): sync_employee_calendar(employee, year)
		if type in SPECIAL: prepare_special(employee,type,start,end,raw)
		elif type != LWP:
			ensure_current_balance(employee)
			ensure_allocation(employee, type, start)
		if type not in {"Maternity Leave", "Paternity Leave"} and leave_year(start)[0] != leave_year(end)[0]: frappe.throw(_("Submit separate leave applications for different leave years."))
		approver = _approver(employee)
		units = sum(units for day, units in leave_units(employee, start, end, raw.get("half_day"), raw.get("half_day_date") or start))
		if policy["director_approval_days"] and units > policy["director_approval_days"] and not exception:
			from volunteering.volunteering.authority import get_fallback_board_approver
			approver = get_fallback_board_approver()
			if not approver: frappe.throw(_("No Board of Directors approver is configured. Contact HR."))
		doc = frappe.get_doc({"doctype": "Leave Application", "employee": employee, "leave_type": type,
			"leave_category": "Normal" if type in SPECIAL else (raw.get("category") or "Normal"), "from_date": start, "to_date": end,
			"description": reason, "status": "Open", "half_day": cint(raw.get("half_day")),
			"half_day_date": raw.get("half_day_date") or (start if raw.get("half_day") else None),
			"leave_approver": approver, "sf_request_key": key, "sf_request_fingerprint": fingerprint, "sf_policy_revision": policy.get("_revision"),
			"sf_manager_notified_on":raw.get("manager_notified_on"),"sf_childbirth_date":raw.get("childbirth_date"),"sf_parental_case":raw.get("parental_case") or ("Birth" if type in {"Maternity Leave","Paternity Leave"} else None)})
		doc.flags.hr_exception_reason = exception
		doc.insert(ignore_permissions=True)
		bind_certificate(doc,raw.get("certificate_url"))
		return _normal_row(doc)
	if type not in TYPES: frappe.throw(_("Choose a valid request type."))
	if type != "Weekly Off Swap" and (end < start or (end-start).days > 90): frappe.throw(_("Choose a date range of at most 90 days."))
	if type in {"Weekly Off Swap", "WFH"} and start < getdate(nowdate()) and not exception:
		frappe.throw(_("Past requests need an HR-authorised exception."))
	if type in {"Compensatory Credit", "Attendance Correction"} and start > getdate(nowdate()): frappe.throw(_("Choose today or a past working date."))
	if type in {"Compensatory Credit", "Attendance Correction"} and start != end: frappe.throw(_("Submit one working date per request."))
	values = {"doctype": "Staff Time Request", "employee": employee,
		"employee_name": frappe.db.get_value("Employee", employee, "employee_name"), "company": frappe.db.get_value("Employee", employee, "company"),
		"request_type": type, "from_date": start, "to_date": end, "reason": reason, "status": "Open",
		"policy_revision": policy.get("_revision"), "request_key": key, "request_fingerprint": fingerprint}
	if type == "Weekly Off Swap":
		_validate_swap(employee, start, end, policy, exception)
	elif type == "Compensatory Credit":
		from volunteering.volunteering.attendance_service import get_submitted_work_log_hours
		from volunteering.volunteering.employee_calendars import holiday_on
		hours = get_submitted_work_log_hours(employee, start)
		if not holiday_on(employee, start) and not exception: frappe.throw(_("This date is not a weekly off or holiday."))
		if hours <= 0 and not exception: frappe.throw(_("Submit a work log for this day before requesting compensatory leave."))
		values["credit_days"] = 1 if hours >= policy["comp_hours"] else (0.5 if hours > 0 and policy["comp_half_day_enabled"] else 0)
		values["requires_hr"] = int(values["credit_days"] == 0)
		values["valid_until"] = getdate(add_months(start, policy["comp_valid_months"]))
		if values["valid_until"] < getdate(nowdate()) and not exception: frappe.throw(_("The compensatory credit window has expired. Contact HR."))
		if frappe.db.exists("Staff Time Request", {"employee": employee, "request_type": type, "from_date": start, "status": ["in", ["Open", "Approved"]]}):
			frappe.throw(_("Compensatory credit was already requested for this workday."))
	elif type == "Attendance Correction":
		if raw.get("requested_status") not in {"Present", "Half Day", "Absent", "Holiday", "Work From Home"}:
			frappe.throw(_("Choose the corrected attendance status."))
		values["requested_status"] = raw["requested_status"]
	if type in {"WFH", "Attendance Correction"} and frappe.db.exists("Staff Time Request", {
		"employee": employee, "request_type": type, "status": ["in", ["Open", "Approved"]],
		"from_date": ["<=", end], "to_date": [">=", start]}):
		frappe.throw(_("There is already an open or approved request for these dates."))
	values["approver"] = _approver(employee, bool(values.get("requires_hr")))
	doc = frappe.get_doc(values); doc.flags.time_service = True; doc.flags.hr_exception_reason = exception
	override_reason(doc); doc.insert(ignore_permissions=True)
	doc.add_comment("Info", _("Request submitted to {0}.").format(doc.approver))
	_notify(doc.approver, doc)
	return _normal_row(doc)


def _validate_swap(employee, work_day, off_day, policy, exception="", exclude=None):
	if (work_day.weekday() != policy["weekly_off_day"] or off_day.weekday() != policy["swap_off_day"]
		or work_day - timedelta(days=work_day.weekday()) != off_day - timedelta(days=off_day.weekday())):
		frappe.throw(_("Choose the usual and alternative weekly off in the same Monday–Sunday week."))
	deadline = work_day - timedelta(days=work_day.weekday()) + timedelta(days=policy["swap_notice_weekday"])
	if not exclude and getdate(nowdate()) > deadline and not exception: frappe.throw(_("This swap needed to be requested by {0}. HR can authorise an exception.").format(deadline))
	filters = {"employee": employee, "request_type": "Weekly Off Swap", "status": ["in", ["Open", "Approved"]], "from_date": work_day}
	if exclude: filters["name"] = ["!=", exclude]
	if frappe.db.exists("Staff Time Request", filters): frappe.throw(_("There is already a swap request for this week."))
	if frappe.db.exists("Staff Time Request", {"employee": employee, "request_type": "Compensatory Credit", "status": ["in", ["Open", "Approved"]], "from_date": work_day}):
		frappe.throw(_("A day cannot be used both for a weekly-off swap and compensatory credit."))
	for day in (work_day, off_day):
		if frappe.db.exists("Leave Application", {"employee": employee, "status": ["in", ["Open", "Approved"]], "docstatus": ["<", 2], "from_date": ["<=", day], "to_date": [">=", day]}):
			frappe.throw(_("Resolve the existing leave application on a swapped date first."))


@frappe.whitelist(methods=["POST"])
def decide_time_request(doctype, name, action, expected_modified, reason="", override="", credit_days=None, valid_until=None):
	from volunteering.volunteering.expense_claim_requests import _retry_snapshot_conflict
	return _retry_snapshot_conflict(lambda: _decide_request(doctype, name, action, expected_modified, reason, override, credit_days, valid_until))


def _decide_request(doctype, name, action, expected_modified, reason="", override="", credit_days=None, valid_until=None):
	if doctype not in {"Leave Application", "Staff Time Request"}: frappe.throw(_("Invalid request."))
	employee = frappe.db.get_value(doctype, name, "employee")
	if not employee: frappe.throw(_("This request is unavailable."))
	lock_employee(employee)
	doc = frappe.get_doc(doctype, name, for_update=True)
	if action not in {"approve", "reject", "cancel", "reverse"}: frappe.throw(_("Choose a valid decision."))
	if action == "cancel":
		if not is_policy_manager() and frappe.db.get_value("Employee", doc.employee, "user_id") != frappe.session.user:
			frappe.throw(_("Only your own open requests can be cancelled."), frappe.PermissionError)
	elif not _can_decide_doc(doc):
		frappe.throw(_("Only the assigned manager or HR can decide this request; self-approval is not allowed."), frappe.PermissionError)
	if action == "reverse":
		require_policy_manager(); reason = reason_text(reason)
		if doc.status != "Approved": frappe.throw(_("Only approved requests can be reversed."))
	else:
		if doc.status != "Open":
			if (action == "approve" and doc.status == "Approved") or (action == "reject" and doc.status == "Rejected") or (action == "cancel" and doc.status == "Cancelled"):
				return _normal_row(doc)
			frappe.throw(_("This request was already decided. Refresh it."))
	if cstr(doc.modified) != cstr(expected_modified): frappe.throw(_("This request changed. Refresh before deciding it."))
	if action in {"reject", "cancel"}: reason = reason_text(reason)
	if override: require_policy_manager(); override = reason_text(override)
	if action in {"approve", "reverse"} and not (doctype == "Staff Time Request" and doc.request_type == "Compensatory Credit"):
		require_unprocessed_salary(doc.employee, min(getdate(doc.from_date), getdate(doc.to_date)), max(getdate(doc.from_date), getdate(doc.to_date)))
	if doctype == "Leave Application":
		if action == "cancel":
			doc.db_set("status", "Cancelled"); sync_comp_uses(doc)
		elif action == "reverse":
			doc.flags.ignore_permissions = True; doc.cancel()
			doc.status = "Cancelled"
		else:
			doc.flags.hr_exception_reason = override
			doc.status = "Approved" if action == "approve" else "Rejected"
			doc.flags.ignore_permissions = True; doc.save(ignore_permissions=True); doc.submit()
		if action != "approve":
			from volunteering.volunteering.attendance_service import process_employee_attendance
			for offset in range((getdate(doc.to_date)-getdate(doc.from_date)).days+1):
				day = getdate(doc.from_date)+timedelta(days=offset)
				if day <= getdate(nowdate()): process_employee_attendance(doc.employee, day)
	else:
		doc.flags.time_service = True
		if action == "reverse" and doc.request_type == "Weekly Off Swap":
			_validate_swap(doc.employee, getdate(doc.from_date), getdate(doc.to_date), policy_on(revision=doc.policy_revision), "Reversal", doc.name)
		if override: doc.flags.hr_exception_reason = override; override_reason(doc)
		if action == "reverse" and doc.request_type == "Compensatory Credit":
			if _used(doc.name) > 0: frappe.throw(_("This credit is reserved or used by leave applications. Resolve them before reversing it."))
			remaining = flt(doc.credit_days) - flt(doc.expired_days)
			if remaining > 0: post_leave(doc.employee, COMP, -remaining, nowdate(), reason, "Credit reversal", doc.name, f"credit-reverse:{doc.name}")
		doc.status = {"approve": "Approved", "reject": "Rejected", "cancel": "Cancelled", "reverse": "Cancelled"}[action]
		if action == "approve":
			if doc.request_type == "Compensatory Credit":
				from volunteering.volunteering.attendance_service import get_submitted_work_log_hours
				from volunteering.volunteering.employee_calendars import holiday_on
				policy = policy_on(doc.from_date, revision=doc.policy_revision)
				hours = get_submitted_work_log_hours(doc.employee, doc.from_date)
				if not override and (not holiday_on(doc.employee, doc.from_date) or hours < (policy["comp_hours"] if doc.credit_days == 1 else 0.001)):
					frappe.throw(_("The supporting holiday or work log changed. HR must review this exception."))
				if credit_days is not None and flt(credit_days) != flt(doc.credit_days):
					if not override: frappe.throw(_("Changing compensatory credit requires an HR exception reason."))
					doc.credit_days = flt(credit_days)
				if valid_until and getdate(valid_until) != getdate(doc.valid_until):
					if not override: frappe.throw(_("Extending validity requires an HR exception reason."))
					doc.valid_until = getdate(valid_until)
				if doc.credit_days not in (0.5, 1) or getdate(doc.valid_until) < getdate(nowdate()): frappe.throw(_("HR must set a half or full compensatory day with valid expiry."))
				posting = post_leave(doc.employee, COMP, doc.credit_days, nowdate(), doc.reason, "Compensatory credit", doc.name, f"credit:{doc.name}")
				doc.leave_adjustment = posting.adjustment
			elif doc.request_type == "Weekly Off Swap":
				_validate_swap(doc.employee, getdate(doc.from_date), getdate(doc.to_date), policy_on(revision=doc.policy_revision), doc.hr_exception_reason, doc.name)
		doc.decision_reason = reason or override; doc.decision_by = frappe.session.user; doc.decision_on = now_datetime()
		doc.save(ignore_permissions=True)
		_refresh_request_attendance(doc)
	doc.add_comment("Info", _("{0} by {1}. {2}").format(action.title(), frappe.session.user, frappe.utils.escape_html(reason or override)))
	_notify(frappe.db.get_value("Employee", doc.employee, "user_id"), doc)
	return _normal_row(doc)


def _refresh_request_attendance(doc):
	from volunteering.volunteering.employee_calendars import clear_calendar_cache, sync_employee_calendar
	from volunteering.volunteering.attendance_service import process_employee_attendance, ensure_attendance, get_submitted_work_log_hours
	clear_calendar_cache()
	for day in {getdate(doc.from_date), getdate(doc.to_date)}:
		if doc.request_type == "Weekly Off Swap": sync_employee_calendar(doc.employee, day.year)
	if doc.request_type == "Attendance Correction" and doc.status == "Approved":
		hours = get_submitted_work_log_hours(doc.employee, doc.from_date)
		name, _action = ensure_attendance(doc.employee, doc.from_date, doc.requested_status, working_hours=hours,
			half_day_status="Absent" if doc.requested_status == "Half Day" else None)
		if name: frappe.db.set_value("Attendance", name, "custom_regularized", 1)
	else:
		start, end = sorted((getdate(doc.from_date), getdate(doc.to_date)))
		if doc.request_type == "Attendance Correction":
			frappe.db.set_value("Attendance", {"employee": doc.employee, "attendance_date": start, "docstatus": 1}, "custom_regularized", 0)
		for offset in range((end-start).days+1):
			day = start + timedelta(days=offset)
			if day <= getdate(nowdate()): process_employee_attendance(doc.employee, day)


def _notify(user, doc):
	if not user or user == frappe.session.user: return
	frappe.get_doc({"doctype": "Notification Log", "for_user": user, "from_user": frappe.session.user,
		"type": "Alert", "subject": f"{doc.doctype} {doc.name}: {doc.status}",
		"document_type": doc.doctype, "document_name": doc.name}).insert(ignore_permissions=True)


def _used(credit, exclude=None):
	filters = {"credit": credit}
	if exclude: filters["application"] = ["!=", exclude]
	return flt(sum(row.days for row in frappe.get_all("Compensatory Leave Use", filters=filters, fields=["days"])))


def _credits(employee, day=None, exclude=None):
	if not employee: return []
	day = getdate(day or nowdate()); rows = []
	for row in frappe.get_all("Staff Time Request", filters={"employee": employee, "request_type": "Compensatory Credit", "status": "Approved"},
		fields=["name", "from_date", "credit_days", "expired_days", "valid_until"], order_by="valid_until asc, creation asc"):
		used = _used(row.name, exclude)
		rows.append({**row, "used": used, "available": max(0, flt(row.credit_days) - used - flt(row.expired_days)) if getdate(row.from_date) < day <= getdate(row.valid_until) else 0})
	return rows


def validate_comp_uses(doc):
	if doc.leave_type != COMP or doc.status not in {"Open", "Approved"}: return
	lock_employee(doc.employee)
	plan = []
	used = {}
	for day, units in leave_units(doc.employee, doc.from_date, doc.to_date, doc.half_day, doc.half_day_date):
		left = units
		for credit in _credits(doc.employee, day, doc.name):
			amount = min(left, max(0, credit["available"] - used.get(credit["name"], 0)))
			if amount:
				plan.append((credit["name"], day, amount)); used[credit["name"]] = used.get(credit["name"], 0) + amount; left -= amount
			if left <= 0: break
		if left > 0: frappe.throw(_("There is not enough unexpired compensatory credit for {0}.").format(day))
	doc.flags.compensatory_plan = plan


def sync_comp_uses(doc, method=None):
	if doc.leave_type != COMP: return
	if doc.docstatus == 2 or doc.status not in {"Open", "Approved"}:
		frappe.db.delete("Compensatory Leave Use", {"application": doc.name})
		return
	plan = doc.flags.get("compensatory_plan")
	if plan is None: return
	frappe.db.delete("Compensatory Leave Use", {"application": doc.name})
	for credit, day, days in plan:
		frappe.get_doc({"doctype": "Compensatory Leave Use", "credit": credit, "application": doc.name,
			"employee": doc.employee, "leave_date": day, "days": days}).insert(ignore_permissions=True)


def expire_compensatory_credits(employee):
	lock_employee(employee)
	for row in frappe.get_all("Staff Time Request", filters={"employee": employee, "request_type": "Compensatory Credit", "status": "Approved", "valid_until": ["<", nowdate()]},
		fields=["name", "credit_days", "expired_days", "valid_until"]):
		left = max(0, flt(row.credit_days) - _used(row.name) - flt(row.expired_days))
		if left:
			from volunteering.volunteering.hr_leave_balances import current_allocation
			expiry_day = getdate(add_days(row.valid_until, 1))
			allocation = current_allocation(employee, COMP, row.valid_until)
			if allocation: expiry_day = min(expiry_day, getdate(allocation.to_date))
			post_leave(employee, COMP, -left, expiry_day, "Unused compensatory credit expired", "Compensatory expiry", row.name, f"expire:{row.name}:{flt(row.expired_days)}")
			frappe.db.set_value("Staff Time Request", row.name, "expired_days", flt(row.expired_days) + left)
