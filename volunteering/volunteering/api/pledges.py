# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Guest-facing Interakt API for De Addiction Pledge confirmation."""

from __future__ import annotations

import base64
import hmac
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from volunteering.volunteering.doctype.de_addiction_pledge_settings.de_addiction_pledge_settings import (
	DEFAULT_CONFIRMATION_TEMPLATE,
	get_pledge_settings,
)
from volunteering.volunteering.doctype.volunteer.volunteer import format_mobile_number

API_KEY_HEADER = "X-Pledge-Api-Key"

# Fields Interakt must send; extra DocType fields in the body are stored automatically.
REQUIRED_TEXT_FIELDS = ("language", "state", "city", "photo_url")
CORE_BODY_FIELDS = frozenset(
	{"mobile_number", "phone", "people_count", "language", "state", "city", "photo_url", "source"}
)
PROTECTED_PLEDGE_FIELDS = frozenset(
	{
		"name",
		"naming_series",
		"pledge_uuid",
		"raw_payload",
		"doctype",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
	}
)
LAYOUT_FIELDTYPES = frozenset(
	{"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading", "Fold"}
)
FIELD_ALIASES = {
	"image": "photo_url",
	"image_url": "photo_url",
	"photo": "photo_url",
	"group_photo": "photo_url",
	"phone": "mobile_number",
}


class PledgeApiError(Exception):
	"""Validation / auth failure returned as a clean JSON body to Interakt / caller."""

	def __init__(self, message: str, status_code: int = 400, extra: dict | None = None):
		self.message = message
		self.status_code = status_code
		self.extra = extra or {}
		super().__init__(message)


def _fail(message: str, status_code: int = 400, extra: dict | None = None) -> None:
	raise PledgeApiError(message, status_code=status_code, extra=extra)


def _error_response(message: str, status_code: int = 400, extra: dict | None = None) -> dict:
	frappe.clear_messages()
	frappe.local.response["http_status_code"] = status_code
	res = {"ok": False, "message": message}
	if extra:
		res.update(extra)
	return res


def _request_args(**kwargs) -> dict:
	"""Merge JSON body and form_dict for guest API calls from Interakt."""
	data: dict[str, Any] = {}
	if frappe.request:
		json_body = frappe.request.get_json(silent=True)
		if isinstance(json_body, dict):
			data.update(json_body)
	data.update(dict(frappe.form_dict or {}))
	data.update({k: v for k, v in kwargs.items() if v is not None})
	data.pop("cmd", None)
	return data


def _assert_api_key(settings=None, data: dict | None = None):
	if frappe.session and frappe.session.user and frappe.session.user != "Guest":
		if "System Manager" in frappe.get_roles() or frappe.session.user == "Administrator":
			return
	settings = settings or get_pledge_settings()
	expected = settings.get_password("api_key", raise_exception=False) or ""
	provided = frappe.get_request_header(API_KEY_HEADER) or ""
	if not provided and data and data.get("api_key"):
		provided = str(data.get("api_key")).strip()
	if not expected or not provided or not hmac.compare_digest(str(expected), str(provided)):
		_fail(_("Invalid API key"), status_code=401)


def _require_non_empty_str(data: dict, key: str, label: str | None = None) -> str:
	label = label or key
	if key not in data or data.get(key) is None:
		_fail(_("{0} is required").format(label))
	text = str(data.get(key)).strip()
	if not text:
		_fail(_("{0} is required").format(label))
	return text


def _require_positive_int(data: dict, key: str, label: str | None = None) -> int:
	label = label or key
	if key not in data or data.get(key) is None or data.get(key) == "":
		_fail(_("{0} is required").format(label))

	raw = data.get(key)
	if isinstance(raw, bool):
		_fail(_("{0} must be a whole number of 1 or more").format(label))

	if isinstance(raw, float):
		if not raw.is_integer():
			_fail(_("{0} must be a whole number of 1 or more").format(label))
		raw = int(raw)
	elif isinstance(raw, str):
		raw = raw.strip()
		if not raw.isdigit():
			_fail(_("{0} must be a whole number of 1 or more").format(label))
		raw = int(raw)
	elif isinstance(raw, int):
		pass
	else:
		_fail(_("{0} must be a whole number of 1 or more").format(label))

	if raw < 1:
		_fail(_("{0} must be a whole number of 1 or more").format(label))
	return raw


def _parse_mobile_number(data: dict) -> str:
	has_mobile = "mobile_number" in data and data.get("mobile_number") is not None
	has_phone = "phone" in data and data.get("phone") is not None
	if not has_mobile and not has_phone:
		_fail(_("mobile_number is required"))

	raw = data.get("mobile_number") if has_mobile else data.get("phone")
	if str(raw).strip() == "":
		_fail(_("mobile_number is required"))

	formatted = format_mobile_number(raw)
	# Require standard Indian mobile: +91-XXXXXXXXXX
	if not formatted or not formatted.startswith("+91-") or len(formatted) != 14:
		_fail(
			_("mobile_number is invalid. Send a 10-digit Indian mobile number (e.g. 9876543210).")
		)
	return formatted


def _apply_extra_doctype_fields(doc, data: dict) -> None:
	"""Copy unknown request keys onto matching writable DocType fields."""
	meta = frappe.get_meta(doc.doctype)
	for key, value in data.items():
		if key in CORE_BODY_FIELDS or key in PROTECTED_PLEDGE_FIELDS or str(key).startswith("_"):
			continue
		df = meta.get_field(key)
		if not df or df.fieldtype in LAYOUT_FIELDTYPES or cint(df.read_only):
			continue
		doc.set(key, value)


def _build_confirmation_message(doc, settings) -> str:
	template = (settings.confirmation_template or "").strip() or DEFAULT_CONFIRMATION_TEMPLATE
	try:
		return template.format(
			pledge_uuid=doc.pledge_uuid or "",
			people_count=cint(doc.people_count),
			mobile_number=doc.mobile_number or "",
			language=doc.language or "",
			state=doc.state or "",
			city=doc.city or "",
		)
	except (KeyError, ValueError, IndexError):
		return DEFAULT_CONFIRMATION_TEMPLATE.format(
			pledge_uuid=doc.pledge_uuid or "",
			people_count=cint(doc.people_count),
		)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def confirm_pledge(**kwargs):
	"""
	Create a De Addiction Pledge with all confirmation details in one call.
	Returns a clean JSON body for Interakt (ok + fields, or ok:false + message).
	"""
	try:
		settings = get_pledge_settings()
		kwargs = _request_args(**kwargs)
		_assert_api_key(settings, kwargs)

		formatted = _parse_mobile_number(kwargs)
		people_count = _require_positive_int(kwargs, "people_count")
		text_fields = {key: _require_non_empty_str(kwargs, key) for key in REQUIRED_TEXT_FIELDS}

		payload = {
			k: v
			for k, v in kwargs.items()
			if k not in {"cmd", "csrf_token"} and not str(k).startswith("_")
		}

		doc = frappe.get_doc(
			{
				"doctype": "De Addiction Pledge",
				"mobile_number": formatted,
				"people_count": people_count,
				"language": text_fields["language"],
				"state": text_fields["state"],
				"city": text_fields["city"],
				"photo_url": text_fields["photo_url"],
				"source": (str(kwargs.get("source")).strip() if kwargs.get("source") else None)
				or "Interakt",
				"raw_payload": json.dumps(payload, default=str, ensure_ascii=False),
			}
		)
		_apply_extra_doctype_fields(doc, kwargs)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		return {
			"ok": True,
			"pledge_uuid": doc.pledge_uuid,
			"name": doc.name,
			"confirmation_message": _build_confirmation_message(doc, settings),
		}
	except PledgeApiError as exc:
		return _error_response(exc.message, status_code=exc.status_code, extra=exc.extra)
	except frappe.AuthenticationError as exc:
		return _error_response(str(exc) or _("Invalid API key"), status_code=401)
	except frappe.ValidationError as exc:
		return _error_response(str(exc) or _("Validation failed"), status_code=400)
	except Exception:
		frappe.log_error(title="confirm_pledge failed")
		return _error_response(_("Something went wrong. Please try again."), status_code=500)


def _handle_image_value(doc, fieldname: str, value: Any) -> Any:
	"""If value is a base64 data URI, save as a Frappe File and return the file_url.
	Otherwise return the string value as-is.
	"""
	if not isinstance(value, str):
		return value

	str_val = value.strip()
	if str_val.startswith("data:image/"):
		try:
			from frappe.utils.file_manager import save_file

			header, b64_data = str_val.split(",", 1)
			mime_part = header.split(";")[0].replace("data:", "")
			ext = mime_part.split("/")[-1].lower() if "/" in mime_part else "jpg"
			if ext in ("jpeg", "jpg"):
				ext = "jpg"
			elif ext == "png":
				ext = "png"
			elif ext == "webp":
				ext = "webp"
			else:
				ext = "jpg"

			file_bytes = base64.b64decode(b64_data)
			file_name = f"{doc.pledge_uuid}_{fieldname}.{ext}"

			saved = save_file(
				file_name,
				file_bytes,
				doc.doctype,
				doc.name,
				df=fieldname,
				is_private=0,
			)
			return saved.file_url
		except Exception as exc:
			_fail(_("Failed to process base64 image: {0}").format(str(exc)), status_code=400)

	return str_val


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_pledge(**kwargs):
	"""
	Update a single field of an existing De Addiction Pledge identified by uuid.
	Takes in uuid (or pledge_uuid), fieldname (or field_name/field), and value.
	If the doc for that uuid doesn't exist, returns a 404 response with exists: False.
	"""
	try:
		settings = get_pledge_settings()
		kwargs = _request_args(**kwargs)
		_assert_api_key(settings, kwargs)

		raw_uuid = kwargs.get("uuid") or kwargs.get("pledge_uuid")
		if raw_uuid is None or str(raw_uuid).strip() == "":
			_fail(_("uuid is required"), status_code=400)
		uuid = str(raw_uuid).strip()

		fieldname = kwargs.get("fieldname") or kwargs.get("field_name") or kwargs.get("field")
		has_value = "value" in kwargs
		value = kwargs.get("value")

		if not fieldname:
			ignored_keys = {
				"uuid",
				"pledge_uuid",
				"fieldname",
				"field_name",
				"field",
				"value",
				"cmd",
				"csrf_token",
				"api_key",
			}
			candidate_keys = [
				k for k in kwargs if k not in ignored_keys and not str(k).startswith("_")
			]
			if len(candidate_keys) == 1:
				fieldname = candidate_keys[0]
				value = kwargs[fieldname]
				has_value = True

		if not fieldname or str(fieldname).strip() == "":
			_fail(_("fieldname is required"), status_code=400)
		if not has_value:
			_fail(_("value is required"), status_code=400)

		fieldname = str(fieldname).strip()

		if fieldname in PROTECTED_PLEDGE_FIELDS:
			_fail(_("Field '{0}' cannot be modified").format(fieldname), status_code=400)

		meta = frappe.get_meta("De Addiction Pledge")

		# Resolve field aliases (e.g. image -> photo_url)
		if not meta.has_field(fieldname) and fieldname in FIELD_ALIASES:
			fieldname = FIELD_ALIASES[fieldname]

		if not meta.has_field(fieldname):
			_fail(
				_("Field '{0}' does not exist on De Addiction Pledge").format(fieldname),
				status_code=400,
			)

		df = meta.get_field(fieldname)
		if df.fieldtype in LAYOUT_FIELDTYPES or cint(df.read_only):
			_fail(_("Field '{0}' cannot be modified").format(fieldname), status_code=400)

		name = frappe.db.get_value("De Addiction Pledge", {"pledge_uuid": uuid}, "name")
		if not name and frappe.db.exists("De Addiction Pledge", uuid):
			name = uuid

		if not name:
			_fail(
				_("Pledge with UUID '{0}' does not exist").format(uuid),
				status_code=404,
				extra={"exists": False, "pledge_uuid": uuid},
			)

		doc = frappe.get_doc("De Addiction Pledge", name)

		# Process image value if applicable (e.g. base64 data URI to saved file URL)
		if fieldname == "photo_url":
			value = _handle_image_value(doc, fieldname, value)
			if value is None or str(value).strip() == "":
				_fail(_("photo_url cannot be empty"), status_code=400)

		# Validate other standard fieldtypes
		if fieldname == "mobile_number":
			formatted = format_mobile_number(value)
			if not formatted or not formatted.startswith("+91-") or len(formatted) != 14:
				_fail(
					_("mobile_number is invalid. Send a 10-digit Indian mobile number (e.g. 9876543210)."),
					status_code=400,
				)
			value = formatted
		elif fieldname == "people_count":
			value = _require_positive_int({"people_count": value}, "people_count")
		elif cint(df.reqd) and (value is None or str(value).strip() == ""):
			_fail(_("{0} cannot be empty").format(df.label or fieldname), status_code=400)

		doc.set(fieldname, value)
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"ok": True,
			"pledge_uuid": doc.pledge_uuid,
			"name": doc.name,
			"fieldname": fieldname,
			"value": doc.get(fieldname),
			"message": _("Field '{0}' updated successfully").format(fieldname),
		}
	except PledgeApiError as exc:
		return _error_response(exc.message, status_code=exc.status_code, extra=exc.extra)
	except frappe.AuthenticationError as exc:
		return _error_response(str(exc) or _("Invalid API key"), status_code=401)
	except frappe.ValidationError as exc:
		return _error_response(str(exc) or _("Validation failed"), status_code=400)
	except Exception:
		frappe.log_error(title="update_pledge failed")
		return _error_response(_("Something went wrong. Please try again."), status_code=500)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_pledge_field(**kwargs):
	"""Alias for update_pledge."""
	return update_pledge(**kwargs)
