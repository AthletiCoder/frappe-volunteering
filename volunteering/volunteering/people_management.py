# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Narrow, role-separated people administration for the staff portal.

HR roles manage Employee records. System Managers manage login accounts and
access roles. The APIs deliberately expose only the fields used by these two
workflows instead of serialising the very large User and Employee documents.
"""

from __future__ import annotations

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.permissions import AUTOMATIC_ROLES
from frappe.utils import cint, cstr, getdate, validate_email_address

SEVAMRITA_COMPANY = "Sevamrita Foundation"
HR_ROLES = frozenset({"HR Manager", "HR User"})
SYSTEM_ROLE = "System Manager"
STANDARD_USERS = frozenset({"Administrator", "Guest"})
EMPLOYEE_STATUSES = frozenset({"Active", "Inactive", "Suspended", "Left"})
USER_TYPES = frozenset({"System User", "Website User"})


def can_manage_employees(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(HR_ROLES.intersection(frappe.get_roles(user)))


def can_manage_users(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or SYSTEM_ROLE in frappe.get_roles(user)


def _require_employee_manager():
	if not can_manage_employees():
		frappe.throw(
			_("Only an HR Manager, HR User or Administrator may manage employees."),
			frappe.PermissionError,
		)


def _require_user_manager():
	if not can_manage_users():
		frappe.throw(
			_("Only a System Manager or Administrator may manage user accounts and roles."),
			frappe.PermissionError,
		)


def _company():
	if frappe.db.exists("Company", SEVAMRITA_COMPANY):
		return SEVAMRITA_COMPANY
	frappe.throw(_("Set up Sevamrita Foundation before managing employees."))


def _text(value, maximum, label=None, required=False):
	value = cstr(value).strip()
	if required and not value:
		frappe.throw(_("{0} is required.").format(label or _("Value")))
	if len(value) > maximum:
		frappe.throw(_("{0} is too long (maximum {1} characters).").format(label or _("Value"), maximum))
	return value


def _check_modified(doc, expected_modified, label):
	if expected_modified and str(doc.modified) != str(expected_modified):
		frappe.throw(_("This {0} changed after you opened it. Refresh and try again.").format(label))


def _names(doctype, filters=None):
	if not frappe.db.exists("DocType", doctype):
		return []
	return frappe.get_all(doctype, filters=filters or {}, pluck="name", order_by="name", limit=1000)


def _employee_fields():
	meta = frappe.get_meta("Employee")
	fields = [
		"name",
		"modified",
		"employee_name",
		"first_name",
		"middle_name",
		"last_name",
		"status",
		"gender",
		"date_of_birth",
		"date_of_joining",
		"relieving_date",
		"user_id",
		"department",
		"designation",
		"employment_type",
		"reports_to",
		"cell_number",
		"company_email",
		"personal_email",
	]
	if meta.has_field("grade"):
		fields.append("grade")
	return [field for field in fields if field in {"name", "modified"} or meta.has_field(field)]


def _employee_row(row):
	result = {field: row.get(field) for field in _employee_fields()}
	manager = result.get("reports_to")
	result["reporting_manager_name"] = (
		frappe.db.get_value("Employee", manager, "employee_name") if manager else ""
	)
	return result


def _employee_options():
	company = _company()
	employees = frappe.get_all(
		"Employee",
		filters={"company": company} if company else {},
		fields=["name", "employee_name", "status", "user_id"],
		order_by="employee_name, name",
		limit=1000,
	)
	linked_users = set(
		frappe.get_all("Employee", filters={"user_id": ["is", "set"]}, pluck="user_id", limit=10000)
	)
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", list(STANDARD_USERS)]},
		fields=["name", "full_name", "user_type"],
		order_by="full_name, name",
		limit=1000,
	)
	return {
		"company": company,
		"genders": _names("Gender"),
		"departments": _names("Department", {"company": company}) if company else _names("Department"),
		"designations": _names("Designation"),
		"grades": _names("Employee Grade"),
		"employment_types": _names("Employment Type"),
		"reporting_managers": employees,
		# An already-linked user remains available while editing that employee;
		# the server still prevents linking it to a second Employee.
		"users": [{**row, "linked": row.name in linked_users} for row in users],
		"statuses": sorted(EMPLOYEE_STATUSES),
	}


@frappe.whitelist(methods=["POST"])
def get_hr_management_workspace():
	_require_employee_manager()
	company = _company()
	fields = [
		"name",
		"employee_name",
		"status",
		"user_id",
		"department",
		"designation",
		"reports_to",
		"date_of_joining",
		"modified",
	]
	if frappe.get_meta("Employee").has_field("grade"):
		fields.append("grade")
	return {
		"can_manage": True,
		"employees": frappe.get_all(
			"Employee",
			filters={"company": company} if company else {},
			fields=fields,
			order_by="employee_name, name",
			limit=1000,
		),
		"options": _employee_options(),
	}


@frappe.whitelist(methods=["POST"])
def get_managed_employee(name):
	_require_employee_manager()
	doc = frappe.get_doc("Employee", cstr(name).strip())
	if doc.company != _company():
		frappe.throw(_("This employee is outside Sevamrita Foundation."), frappe.PermissionError)
	return _employee_row(doc)


def _employee_values(details):
	raw = frappe.parse_json(details) if isinstance(details, str) else details
	if not isinstance(raw, dict):
		frappe.throw(_("Employee details must be a valid object."))
	status = _text(raw.get("status") or "Active", 20, _("Status"), required=True)
	if status not in EMPLOYEE_STATUSES:
		frappe.throw(_("Choose a valid employee status."))
	values = {
		"first_name": _text(raw.get("first_name"), 140, _("First name"), required=True),
		"middle_name": _text(raw.get("middle_name"), 140, _("Middle name")),
		"last_name": _text(raw.get("last_name"), 140, _("Last name")),
		"status": status,
		"gender": _text(raw.get("gender"), 140, _("Gender"), required=True),
		"date_of_birth": getdate(raw.get("date_of_birth")) if raw.get("date_of_birth") else None,
		"date_of_joining": getdate(raw.get("date_of_joining")) if raw.get("date_of_joining") else None,
		"relieving_date": getdate(raw.get("relieving_date")) if raw.get("relieving_date") else None,
		"user_id": _text(raw.get("user_id"), 140, _("User ID")),
		"department": _text(raw.get("department"), 140, _("Department")),
		"designation": _text(raw.get("designation"), 140, _("Designation")),
		"employment_type": _text(raw.get("employment_type"), 140, _("Employment type")),
		"reports_to": _text(raw.get("reports_to"), 140, _("Reports to")),
		"cell_number": _text(raw.get("cell_number"), 40, _("Mobile")),
		"company_email": _text(raw.get("company_email"), 140, _("Company email")),
		"personal_email": _text(raw.get("personal_email"), 140, _("Personal email")),
	}
	if not values["date_of_birth"]:
		frappe.throw(_("Date of birth is required."))
	if not values["date_of_joining"]:
		frappe.throw(_("Date of joining is required."))
	if status == "Left" and not values["relieving_date"]:
		frappe.throw(_("Relieving date is required when the employee status is Left."))
	for field in ("company_email", "personal_email"):
		if values[field]:
			validate_email_address(values[field], throw=True)
	if values["user_id"]:
		if values["user_id"] in STANDARD_USERS or not frappe.db.exists("User", values["user_id"]):
			frappe.throw(_("Choose an existing non-standard User account."))
	if frappe.get_meta("Employee").has_field("grade"):
		values["grade"] = _text(raw.get("grade"), 140, _("Grade"))
	return values


@frappe.whitelist(methods=["POST"])
def save_managed_employee(details, name=None, expected_modified=None):
	_require_employee_manager()
	company = _company()
	if not company:
		frappe.throw(_("Set up Sevamrita Foundation before adding employees."))
	values = _employee_values(details)
	if name:
		doc = frappe.get_doc("Employee", cstr(name).strip())
		if doc.company != company:
			frappe.throw(_("This employee is outside Sevamrita Foundation."), frappe.PermissionError)
		_check_modified(doc, expected_modified, _("employee"))
	else:
		doc = frappe.new_doc("Employee")
		doc.company = company
	if values.get("reports_to") and values["reports_to"] == doc.name:
		frappe.throw(_("An employee cannot report to themselves."))
	if values.get("user_id"):
		other = frappe.db.get_value("Employee", {"user_id": values["user_id"]}, "name")
		if other and other != doc.name:
			frappe.throw(_("That User account is already linked to employee {0}.").format(other))
	for field, value in values.items():
		if frappe.get_meta("Employee").has_field(field):
			doc.set(field, value)
	doc.flags.ignore_permissions = True
	doc.save()
	return {"employee": _employee_row(doc), "workspace": get_hr_management_workspace()}


def _available_roles():
	return frappe.get_all(
		"Role",
		filters={"disabled": 0, "name": ["not in", list(AUTOMATIC_ROLES)]},
		fields=["name", "desk_access"],
		order_by="name",
		limit=1000,
	)


def _role_profiles():
	if not frappe.db.exists("DocType", "Role Profile"):
		return []
	result = []
	for name in _names("Role Profile"):
		doc = frappe.get_doc("Role Profile", name)
		result.append({"name": name, "roles": sorted({row.role for row in doc.roles})})
	return result


def _user_row(row):
	employee = frappe.db.get_value(
		"Employee", {"user_id": row.name}, ["name", "employee_name", "status"], as_dict=True
	)
	return {
		"name": row.name,
		"full_name": row.full_name,
		"enabled": cint(row.enabled),
		"user_type": row.user_type,
		"modified": row.modified,
		"employee": employee,
	}


def _user_detail(doc):
	row = _user_row(doc)
	row.update(
		{
			"first_name": doc.first_name,
			"middle_name": doc.middle_name,
			"last_name": doc.last_name,
			"roles": sorted({item.role for item in doc.roles if item.role not in AUTOMATIC_ROLES}),
			"role_profiles": sorted({item.role_profile for item in (doc.get("role_profiles") or [])}),
		}
	)
	return row


@frappe.whitelist(methods=["POST"])
def get_system_management_workspace():
	_require_user_manager()
	rows = frappe.get_all(
		"User",
		filters={"name": ["not in", list(STANDARD_USERS)]},
		fields=["name", "full_name", "enabled", "user_type", "modified"],
		order_by="full_name, name",
		limit=1000,
	)
	return {
		"can_manage": True,
		"users": [_user_row(row) for row in rows],
		"roles": _available_roles(),
		"role_profiles": _role_profiles(),
		"user_types": sorted(USER_TYPES),
	}


@frappe.whitelist(methods=["POST"])
def get_managed_user(name):
	_require_user_manager()
	name = cstr(name).strip()
	if name in STANDARD_USERS:
		frappe.throw(_("Standard system users are not editable from this portal."), frappe.PermissionError)
	return _user_detail(frappe.get_doc("User", name))


def _selected_names(values: Iterable | str | None):
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, (list, tuple, set)):
		return []
	selected = set()
	for value in values:
		value = _text(value, 140)
		if value:
			selected.add(value)
	return sorted(selected)


def _validate_access_selection(raw):
	mode = cstr(raw.get("role_mode") or "roles").strip()
	if mode not in {"roles", "profiles"}:
		frappe.throw(_("Choose direct roles or role profiles."))
	roles = _selected_names(raw.get("roles"))
	profiles = _selected_names(raw.get("role_profiles"))
	allowed_roles = {row.name for row in _available_roles()}
	allowed_profiles = set(_names("Role Profile"))
	if set(roles) - allowed_roles:
		frappe.throw(_("One or more selected roles are unavailable."))
	if set(profiles) - allowed_profiles:
		frappe.throw(_("One or more selected role profiles are unavailable."))
	return mode, roles, profiles


def _effective_roles(mode, roles, profiles):
	if mode == "roles":
		return set(roles)
	result = set()
	for profile in profiles:
		result.update(row.role for row in frappe.get_doc("Role Profile", profile).roles)
	return result


@frappe.whitelist(methods=["POST"])
def save_managed_user(details, name=None, expected_modified=None):
	_require_user_manager()
	raw = frappe.parse_json(details) if isinstance(details, str) else details
	if not isinstance(raw, dict):
		frappe.throw(_("User details must be a valid object."))
	first_name = _text(raw.get("first_name"), 140, _("First name"), required=True)
	middle_name = _text(raw.get("middle_name"), 140, _("Middle name"))
	last_name = _text(raw.get("last_name"), 140, _("Last name"))
	enabled = cint(raw.get("enabled"))
	requested_type = _text(raw.get("user_type") or "System User", 40, _("User type"), required=True)
	if requested_type not in USER_TYPES:
		frappe.throw(_("Choose System User or Website User."))
	mode, roles, profiles = _validate_access_selection(raw)
	effective_roles = _effective_roles(mode, roles, profiles)

	if name:
		name = cstr(name).strip()
		if name in STANDARD_USERS:
			frappe.throw(
				_("Standard system users are not editable from this portal."), frappe.PermissionError
			)
		doc = frappe.get_doc("User", name)
		_check_modified(doc, expected_modified, _("user"))
	else:
		email = _text(raw.get("email"), 140, _("Email"), required=True).lower()
		validate_email_address(email, throw=True)
		if email in STANDARD_USERS or frappe.db.exists("User", email):
			frappe.throw(_("A User with that email already exists."))
		doc = frappe.new_doc("User")
		doc.email = email
		doc.send_welcome_email = cint(raw.get("send_welcome_email"))

	# ERPNext derives the Employee role from an Employee → User link. A direct
	# role edit must not silently remove that access. A Role Profile must contain
	# Employee itself because Frappe replaces the User's roles from the profile.
	linked_employee = frappe.db.exists("Employee", {"user_id": doc.name}) if doc.name else None
	if linked_employee and "Employee" not in effective_roles:
		if mode == "profiles":
			frappe.throw(_("A linked employee needs a Role Profile that includes the Employee role."))
		roles = sorted({*roles, "Employee"})
		effective_roles.add("Employee")

	if doc.name == frappe.session.user:
		if not enabled:
			frappe.throw(_("You cannot disable your own account."))
		if SYSTEM_ROLE in frappe.get_roles(frappe.session.user) and SYSTEM_ROLE not in effective_roles:
			frappe.throw(_("You cannot remove your own System Manager access."))

	doc.first_name = first_name
	doc.middle_name = middle_name
	doc.last_name = last_name
	doc.enabled = enabled
	doc.user_type = requested_type
	doc.set("roles", [])
	doc.set("role_profiles", [])
	if mode == "profiles":
		for profile in profiles:
			doc.append("role_profiles", {"role_profile": profile})
	else:
		for role in roles:
			doc.append("roles", {"role": role})
	doc.flags.ignore_permissions = True
	doc.save()
	# Other installed apps may add roles in after_insert hooks. Reload so the
	# editor reflects the actual stored access rather than its pre-hook state.
	return {
		"user": _user_detail(frappe.get_doc("User", doc.name)),
		"workspace": get_system_management_workspace(),
	}
