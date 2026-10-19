# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Guest-facing Interakt API for De Addiction Pledge confirmation."""

from __future__ import annotations

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


class PledgeApiError(Exception):
	"""Validation / auth failure returned as a clean JSON body to Interakt."""

	def __init__(self, message: str, status_code: int = 400):
		self.message = message
		self.status_code = status_code
		super().__init__(message)


def _fail(message: str, status_code: int = 400) -> None:
	raise PledgeApiError(message, status_code=status_code)


def _error_response(message: str, status_code: int = 400) -> dict:
	frappe.clear_messages()
	frappe.local.response["http_status_code"] = status_code
	return {"ok": False, "message": message}


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


def _assert_api_key(settings=None):
	settings = settings or get_pledge_settings()
	expected = settings.get_password("api_key", raise_exception=False) or ""
	provided = frappe.get_request_header(API_KEY_HEADER) or ""
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


def _build_confirmation_message(doc, settings) -> str:
	template = (settings.confirmation_template or "").strip() or DEFAULT_CONFIRMATION_TEMPLATE
	try:
		return template.format(
			pledge_uuid=doc.pledge_uuid or "",
			people_count=cint(doc.people_count),
			mobile_number=doc.mobile_number or "",
			language=doc.language or "",
			state=doc.state or "",
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
		_assert_api_key(settings)
		kwargs = _request_args(**kwargs)

		formatted = _parse_mobile_number(kwargs)
		people_count = _require_positive_int(kwargs, "people_count")
		language = _require_non_empty_str(kwargs, "language")
		state = _require_non_empty_str(kwargs, "state")
		photo_url = _require_non_empty_str(kwargs, "photo_url")

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
				"language": language,
				"state": state,
				"photo_url": photo_url,
				"source": (str(kwargs.get("source")).strip() if kwargs.get("source") else None)
				or "Interakt",
				"raw_payload": json.dumps(payload, default=str, ensure_ascii=False),
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		return {
			"ok": True,
			"pledge_uuid": doc.pledge_uuid,
			"name": doc.name,
			"confirmation_message": _build_confirmation_message(doc, settings),
		}
	except PledgeApiError as exc:
		return _error_response(exc.message, status_code=exc.status_code)
	except frappe.AuthenticationError as exc:
		return _error_response(str(exc) or _("Invalid API key"), status_code=401)
	except frappe.ValidationError as exc:
		return _error_response(str(exc) or _("Validation failed"), status_code=400)
	except Exception:
		frappe.log_error(title="confirm_pledge failed")
		return _error_response(_("Something went wrong. Please try again."), status_code=500)
