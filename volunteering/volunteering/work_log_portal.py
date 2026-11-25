"""Session-scoped work logging for Home and the native app."""

from decimal import Decimal, InvalidOperation
from calendar import monthrange
from datetime import date as date_type, timedelta
import re
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, getdate, nowdate

from volunteering.volunteering.daily_work_log_permissions import HR_ROLES, can_review_work_log
from volunteering.volunteering.doctype.daily_work_log.daily_work_log import get_daily_work_log_settings


def work_logging_access():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Sign in to view work logs."), frappe.PermissionError)
	employee = frappe.db.get_value(
		"Employee", {"user_id": user, "status": "Active"}, ["name", "employee_name"], as_dict=True,
	)
	is_hr = user == "Administrator" or bool(HR_ROLES.intersection(frappe.get_roles(user)))
	has_team = bool(employee and frappe.db.exists("Employee", {"reports_to": employee.name}))
	return {"employee": employee, "can_create": bool(employee), "can_review_team": is_hr or has_team, "is_hr": is_hr}


@frappe.whitelist(methods=["POST"])
def get_tasks_app_access():
	from volunteering.volunteering.collaboration_access import has_app_chat_access
	access = work_logging_access()
	chat_access = has_app_chat_access()
	if not chat_access and not access["can_create"] and not access["can_review_team"]:
		frappe.throw(_("Your account needs App chat access or work logging access."), frappe.PermissionError)
	return {"work_logging": access, "chat_access": chat_access}


def _access():
	access = work_logging_access()
	if not access["can_create"] and not access["can_review_team"]:
		frappe.throw(_("Your account needs an active employee record to log work."), frappe.PermissionError)
	return access


def _options(access):
	settings = get_daily_work_log_settings()
	from volunteering.volunteering.hr_policy import is_policy_manager, policy_on
	policy = policy_on()
	return {
		**access, "today": nowdate(),
		"can_override": is_policy_manager(),
		"earliest_date": str(add_days(nowdate(), -policy["work_log_days"])),
		"recommended_hours": policy["full_day_hours"],
		"projects": frappe.get_list(
			"Project", filters={"status": "Open"}, fields=["name", "project_name"],
			order_by="project_name asc", limit_page_length=0,
		) if access["can_create"] and frappe.has_permission("Project", "read") else [],
	}


@frappe.whitelist(methods=["POST"])
def get_work_log_access():
	return _options(_access())


def _scope(access, view):
	own = (access["employee"] or {}).get("name")
	if view == "mine":
		return {"employee": own or "__no_employee__"}
	if view != "team" or not access["can_review_team"]:
		frappe.throw(_("You cannot view this work log list."), frappe.PermissionError)
	if access["is_hr"]:
		return {"employee": ["!=", own]} if own else {}
	reports = frappe.get_all("Employee", filters={"reports_to": own}, pluck="name", limit_page_length=0)
	return {"employee": ["in", reports or ["__no_reports__"]]}


def _month(value):
	value = cstr(value or nowdate()[:7])
	if not re.fullmatch(r"\d{4}-\d{2}", value):
		frappe.throw(_("Choose a valid month."))
	try:
		year, month = map(int, value.split("-"))
		return date_type(year, month, 1), date_type(year, month, monthrange(year, month)[1])
	except (ValueError, OverflowError):
		frappe.throw(_("Choose a valid month."))


def _calendar_employee(access, employee):
	own = (access["employee"] or {}).get("name")
	target = employee or own
	person = frappe.db.get_value("Employee", target, ["name", "employee_name", "date_of_joining", "relieving_date", "reports_to"], as_dict=True) if target else None
	if not person or (target != own and not access["is_hr"] and person.reports_to != own):
		frappe.throw(_("You cannot access this employee's work logs."), frappe.PermissionError)
	return person


@frappe.whitelist(methods=["POST"])
def get_work_log_calendar(month="", employee=""):
	access = _access()
	person = _calendar_employee(access, employee)
	first, last = _month(month)
	today = getdate(nowdate())
	options = _options(access)
	earliest = getdate(options["earliest_date"])
	own = person.name == (access["employee"] or {}).get("name")
	rows = frappe.get_all(
		"Daily Work Log", filters={"employee": person.name, "date": ["between", [first, last]]},
		fields=["name", "date", "status", "docstatus", "total_hours"],
		order_by="docstatus asc, creation desc", limit_page_length=0,
	)
	by_date = {}
	for row in rows:
		by_date.setdefault(getdate(row.date), row)
	leaves = frappe.get_all("Leave Application", filters={"employee": person.name, "docstatus": 1, "status": "Approved", "from_date": ["<=", last], "to_date": [">=", first]}, fields=["leave_type", "from_date", "to_date", "half_day", "half_day_date"])
	days, summary = [], {"Not filled": 0, "Draft": 0, "Submitted": 0, "Reviewed": 0, "total_hours": 0}
	for offset in range((last - first).days + 1):
		day = first + timedelta(days=offset)
		row = by_date.get(day)
		active = bool(row and row.docstatus < 2)
		in_employment = (not person.date_of_joining or day >= getdate(person.date_of_joining)) and (not person.relieving_date or day <= getdate(person.relieving_date))
		status = row.status if active else "Not filled"
		if day > today:
			status = "Future"
		elif not in_employment and not active:
			status = "Outside employment"
		hours = row.total_hours if active else None
		from volunteering.volunteering.attendance_service import get_holiday_info
		holiday = get_holiday_info(person.name, day)
		leave = next((leave for leave in leaves if getdate(leave.from_date) <= day <= getdate(leave.to_date)), None)
		half = bool(leave and leave.half_day and getdate(leave.half_day_date or leave.from_date) == day)
		if not active and status == "Not filled":
			if holiday: status = "Holiday"
			elif leave and not half: status = "On leave"
		if status in summary:
			summary[status] += 1
			summary["total_hours"] += hours or 0
		days.append({"date": str(day), "status": status, "total_hours": hours,
			"day_note": (holiday.get("description") if holiday else "") or (("Half-day " if half else "") + leave.leave_type if leave else ""),
			"name": row.name if row else "", "cancelled": bool(row and not active),
			"can_open": day <= today and bool(row or (in_employment and ((own and day >= earliest) or options["can_override"])))})
	summary["submitted_total"] = summary["Submitted"] + summary["Reviewed"]
	summary["awaiting_review"] = summary["Submitted"]
	return {**options, "month": first.strftime("%Y-%m"), "calendar_employee": person,
		"days": days, "summary": summary, "is_own": own}


@frappe.whitelist(methods=["POST"])
def get_work_log_team(month="", query="", page=1):
	access = _access()
	filters = _scope(access, "team")
	first, last = _month(month)
	query = cstr(query).strip()[:100]
	page = max(1, cint(page))
	people = frappe.get_all("Employee", filters=filters,
		or_filters={"employee_name": ["like", f"%{query}%"], "name": ["like", f"%{query}%"]} if query else None,
		fields=["name", "employee_name", "designation", "status"], order_by="employee_name asc, name asc",
		start=(page - 1) * 30, limit=31)
	names = [row.name for row in people[:30]]
	counts = {name: {"submitted": 0, "draft": 0, "reviewed": 0, "total_hours": 0} for name in names}
	if names:
		for row in frappe.get_all("Daily Work Log", filters={"employee": ["in", names], "date": ["between", [first, min(last, getdate(nowdate()))]], "docstatus": ["<", 2]}, fields=["employee", "status", "total_hours"], limit_page_length=0):
			count = counts[row.employee]
			key = row.status.lower()
			if key in count:
				count[key] += 1
			count["total_hours"] += row.total_hours or 0
	for person in people[:30]:
		person.update(counts[person.name])
	return {**_options(access), "month": first.strftime("%Y-%m"), "people": people[:30], "page": page, "has_more": len(people) > 30, "query": query}


@frappe.whitelist(methods=["POST"])
def get_work_log_workspace(view="mine", status="", page=1, from_date="", to_date=""):
	access = _access()
	filters = _scope(access, view)
	if status:
		if status not in ("Draft", "Submitted", "Reviewed", "Cancelled"):
			frappe.throw(_("Choose a valid work log status."))
		filters["status"] = status
	if from_date:
		filters["date"] = [">=", getdate(from_date)]
	if to_date:
		filters["date"] = ["between", [getdate(from_date), getdate(to_date)]] if from_date else ["<=", getdate(to_date)]
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("The end date must follow the start date."))
	page = max(1, cint(page))
	rows = frappe.get_all(
		"Daily Work Log", filters=filters,
		fields=["name", "employee_name", "date", "status", "total_hours", "modified"],
		order_by="date desc, name desc", start=(page - 1) * 20, limit=21,
	)
	names = [row.name for row in rows[:20]]
	previews = {}
	if names:
		for item in frappe.get_all(
			"Daily Work Log Item", filters={"parent": ["in", names], "parenttype": "Daily Work Log"},
			fields=["parent", "task_title"], order_by="idx asc", limit_page_length=0,
		):
			previews.setdefault(item.parent, []).append(item.task_title)
	for row in rows[:20]:
		row["tasks"] = previews.get(row.name, [])
	return {**_options(access), "rows": rows[:20], "page": page, "has_more": len(rows) > 20, "view": view}


def _load(name, access, lock=False):
	doc = frappe.get_doc("Daily Work Log", name, for_update=lock)
	own = (access["employee"] or {}).get("name")
	if doc.employee != own and not can_review_work_log(doc):
		frappe.throw(_("You cannot access this employee's work log."), frappe.PermissionError)
	return doc


def _payload(doc, access):
	own = (access["employee"] or {}).get("name")
	can_review = bool(doc.docstatus == 1 and doc.status == "Submitted" and can_review_work_log(doc))
	data = {
		key: doc.get(key) for key in
		("name", "employee", "employee_name", "date", "status", "docstatus", "total_hours", "notes", "is_wfh")
	}
	data.update({
		"modified": str(doc.modified), "can_edit": doc.docstatus == 0 and (doc.employee == own or _options(access)["can_override"]),
		"hr_exception_reason": doc.get("hr_exception_reason") or "",
		"is_own": doc.employee == own,
		"can_review": can_review,
		"items": [
			{key: row.get(key) for key in ("task_title", "project", "description", "time_spent_hours", "output_link")}
			for row in doc.items
		],
	})
	# Manager remarks retain the existing private visibility.
	if access["is_hr"] or (doc.employee != own and can_review_work_log(doc)):
		data["manager_remarks"] = doc.manager_remarks
	for item in data["items"]:
		item["project_name"] = frappe.db.get_value("Project", item["project"], "project_name") if item["project"] else ""
	return data


@frappe.whitelist(methods=["POST"])
def get_work_log(name="", date="", employee=""):
	access = _access()
	if not name:
		person = _calendar_employee(access, employee)
		if person.name != (access["employee"] or {}).get("name") and not _options(access)["can_override"]:
			frappe.throw(_("Only HR Managers can log work for another employee."), frappe.PermissionError)
		date = getdate(date or nowdate())
		if date > getdate(nowdate()):
			frappe.throw(_("Work cannot be logged for a future date."))
		name = frappe.db.get_value(
			"Daily Work Log", {"employee": person.name, "date": date, "docstatus": ["<", 2]}, "name",
		)
	if name:
		log = _payload(_load(name, access), access)
	else:
		log = {
			"name": "", "date": str(date), "modified": "", "employee_name": person.employee_name,
			"employee": person.name, "is_own": person.name == (access["employee"] or {}).get("name"),
			"status": "Draft", "can_edit": True, "can_review": False, "notes": "", "total_hours": 0,
			"items": [{"task_title": "", "project": "", "description": "", "time_spent_hours": "", "output_link": ""}],
		}
	from volunteering.volunteering.attendance_service import has_approved_wfh_request_for_employee
	log["is_wfh"] = has_approved_wfh_request_for_employee(log.get("employee") or access["employee"].name, str(log["date"]))
	return {**_options(access), "log": log}


def _text(value, label, limit):
	text = cstr(value or "").strip()
	if len(text) > limit:
		frappe.throw(_("{0} must be at most {1} characters.").format(label, limit))
	return text


def _items(raw, previous_projects):
	if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
		frappe.throw(_("Add between one and 100 work items."))
	items = []
	for row in raw:
		if not isinstance(row, dict):
			frappe.throw(_("Enter valid work items."))
		try:
			hours = Decimal(str(row.get("time_spent_hours", "")))
		except (InvalidOperation, TypeError, ValueError):
			frappe.throw(_("Enter valid hours for each work item."))
		if not hours.is_finite() or hours <= 0 or hours > 24:
			frappe.throw(_("Each work item needs hours greater than zero and at most 24."))
		link = _text(row.get("output_link"), "Output link", 2048)
		if link and (urlparse(link).scheme not in ("https", "http") or not urlparse(link).netloc):
			frappe.throw(_("Output links must start with https:// or http://."))
		project = _text(row.get("project"), "Project", 140)
		if project and project not in previous_projects and not frappe.has_permission("Project", "read", doc=project):
			frappe.throw(_("Choose a project you have access to."), frappe.PermissionError)
		items.append({
			"task_title": _text(row.get("task_title"), "Task title", 140),
			"description": _text(row.get("description"), "Description", 4000),
			"project": project, "time_spent_hours": float(hours), "output_link": link,
		})
	return items


def _check_version(doc, expected_modified):
	if not expected_modified or str(doc.modified) != cstr(expected_modified):
		frappe.throw(_("This work log changed. Reopen it before saving."), frappe.TimestampMismatchError)


@frappe.whitelist(methods=["POST"])
def save_work_log(details, submit=0):
	access = _access()
	if not access["can_create"] and not _options(access)["can_override"]:
		frappe.throw(_("An active employee record is required."), frappe.PermissionError)
	raw = frappe.parse_json(details)
	if not isinstance(raw, dict) or not raw.get("date"):
		frappe.throw(_("Enter a work log date and items."))
	date = getdate(raw["date"])
	from volunteering.volunteering.hr_policy import is_policy_manager, reason_text
	own = (access["employee"] or {}).get("name")
	target = raw.get("employee") or own
	_calendar_employee(access, target)
	exception = reason_text(raw["hr_exception_reason"]) if raw.get("hr_exception_reason") else ""
	if (target != own or exception) and not is_policy_manager():
		frappe.throw(_("Only HR Managers can authorise a work-log exception."), frappe.PermissionError)
	if target != own and not exception:
		frappe.throw(_("Explain the HR exception before logging work for another employee."))
	if date > getdate(nowdate()):
		frappe.throw(_("Work cannot be logged for a future date."))
	# Serialize per employee, including first submissions and retrying a new form.
	frappe.db.get_value("Employee", target, "name", for_update=True)
	name = raw.get("name") or frappe.db.get_value(
		"Daily Work Log", {"employee": target, "date": date, "docstatus": ["<", 2]}, "name",
	)
	if name:
		doc = _load(name, access, lock=True)
		if doc.employee != target:
			frappe.throw(_("You can only edit your own work log."), frappe.PermissionError)
		stored_items = [
			{key: (row.get(key) or "") for key in ("task_title", "project", "description", "output_link")}
			| {"time_spent_hours": float(row.time_spent_hours)}
			for row in doc.items
		]
		incoming = _items(raw.get("items"), {item.project for item in doc.items})
		same_contents = incoming == stored_items and cstr(raw.get("notes") or "").strip() == (doc.notes or "") and date == getdate(doc.date)
		if same_contents and ((doc.docstatus == 1 and cint(submit)) or (doc.docstatus == 0 and not cint(submit))):
			return get_work_log(name=doc.name)
		if doc.docstatus != 0:
			frappe.throw(_("Only draft logs can be edited."))
		_check_version(doc, raw.get("modified"))
		if getdate(doc.date) != date:
			frappe.throw(_("The date of a saved log cannot be changed."))
	else:
		doc = frappe.new_doc("Daily Work Log")
		doc.employee = target
		doc.date = date
	previous_projects = {item.project for item in doc.items}
	doc.notes = _text(raw.get("notes"), "Notes", 4000)
	doc.flags.hr_exception_reason = exception
	doc.set("items", _items(raw.get("items"), previous_projects))
	doc.save(ignore_permissions=bool(exception))
	if cint(submit):
		doc.flags.ignore_permissions = bool(exception)
		doc.submit()
	doc.reload()
	return get_work_log(name=doc.name)


@frappe.whitelist(methods=["POST"])
def review_work_log(name, expected_modified, remarks=""):
	access = _access()
	doc = _load(name, access, lock=True)
	if not can_review_work_log(doc):
		frappe.throw(_("Only the reporting manager or HR can review this log."), frappe.PermissionError)
	if doc.status == "Reviewed":
		return get_work_log(name=doc.name)
	_check_version(doc, expected_modified)
	doc.mark_as_reviewed(manager_remarks=_text(remarks, "Review notes", 4000))
	return get_work_log(name=doc.name)
