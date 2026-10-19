# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Guest-facing Interakt APIs for De Addiction Pledge."""

from __future__ import annotations

import hmac
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from volunteering.volunteering.doctype.de_addiction_pledge_settings.de_addiction_pledge_settings import (
	DEFAULT_CONFIRMATION_TEMPLATE,
	get_pledge_settings,
)
from volunteering.volunteering.doctype.volunteer.volunteer import format_mobile_number

API_KEY_HEADER = "X-Pledge-Api-Key"


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
		frappe.throw(_("Invalid API key"), frappe.AuthenticationError)


def _require_non_empty_str(data: dict, key: str, label: str | None = None) -> str:
	label = label or key
	if key not in data or data.get(key) is None:
		frappe.throw(_("{0} is required").format(label))
	text = str(data.get(key)).strip()
	if not text:
		frappe.throw(_("{0} is required").format(label))
	return text


def _require_positive_int(data: dict, key: str, label: str | None = None) -> int:
	label = label or key
	if key not in data or data.get(key) is None or data.get(key) == "":
		frappe.throw(_("{0} is required").format(label))

	raw = data.get(key)
	if isinstance(raw, bool):
		frappe.throw(_("{0} must be a whole number of 1 or more").format(label))

	if isinstance(raw, float):
		if not raw.is_integer():
			frappe.throw(_("{0} must be a whole number of 1 or more").format(label))
		raw = int(raw)
	elif isinstance(raw, str):
		raw = raw.strip()
		if not raw.isdigit():
			frappe.throw(_("{0} must be a whole number of 1 or more").format(label))
		raw = int(raw)
	elif isinstance(raw, int):
		pass
	else:
		frappe.throw(_("{0} must be a whole number of 1 or more").format(label))

	if raw < 1:
		frappe.throw(_("{0} must be a whole number of 1 or more").format(label))
	return raw


def _parse_mobile_number(data: dict) -> str:
	has_mobile = "mobile_number" in data and data.get("mobile_number") is not None
	has_phone = "phone" in data and data.get("phone") is not None
	if not has_mobile and not has_phone:
		frappe.throw(_("mobile_number is required"))

	raw = data.get("mobile_number") if has_mobile else data.get("phone")
	if str(raw).strip() == "":
		frappe.throw(_("mobile_number is required"))

	formatted = format_mobile_number(raw)
	# Require standard Indian mobile: +91-XXXXXXXXXX
	if not formatted or not formatted.startswith("+91-") or len(formatted) != 14:
		frappe.throw(
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


def _get_pledge_by_uuid(pledge_uuid: str):
	name = frappe.db.get_value("De Addiction Pledge", {"pledge_uuid": pledge_uuid}, "name")
	if not name:
		frappe.throw(
			_("No pledge found for pledge_uuid '{0}'").format(pledge_uuid),
			frappe.DoesNotExistError,
		)
	return frappe.get_doc("De Addiction Pledge", name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def start_pledge(**kwargs):
	"""
	Create a Draft De Addiction Pledge when Interakt chat starts.
	Returns pledge_uuid for Interakt to send back on complete.
	"""
	settings = get_pledge_settings()
	_assert_api_key(settings)
	kwargs = _request_args(**kwargs)

	formatted = _parse_mobile_number(kwargs)

	doc = frappe.get_doc(
		{
			"doctype": "De Addiction Pledge",
			"mobile_number": formatted,
			"status": "Draft",
			"source": (str(kwargs.get("source")).strip() if kwargs.get("source") else None)
			or "Interakt",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"pledge_uuid": doc.pledge_uuid,
		"name": doc.name,
		"status": doc.status,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def complete_pledge(**kwargs):
	"""
	Update pledge with Interakt completion details and return confirmation text.
	Last-write-wins on details; always returns confirmation_message for retries.
	"""
	settings = get_pledge_settings()
	_assert_api_key(settings)
	kwargs = _request_args(**kwargs)

	pledge_uuid = _require_non_empty_str(kwargs, "pledge_uuid")
	people_count = _require_positive_int(kwargs, "people_count")
	language = _require_non_empty_str(kwargs, "language")
	state = _require_non_empty_str(kwargs, "state")

	doc = _get_pledge_by_uuid(pledge_uuid)
	doc.people_count = people_count
	doc.language = language
	doc.state = state

	# Persist last payload for debugging (photo handling deferred)
	payload = {
		k: v
		for k, v in kwargs.items()
		if k not in {"cmd", "csrf_token"} and not str(k).startswith("_")
	}
	doc.raw_payload = json.dumps(payload, default=str, ensure_ascii=False)

	now = now_datetime()
	if doc.status != "Completed":
		doc.status = "Completed"
		doc.completed_on = now

	doc.confirmation_sent = 1
	doc.confirmation_sent_on = now
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	confirmation_message = _build_confirmation_message(doc, settings)

	return {
		"pledge_uuid": doc.pledge_uuid,
		"name": doc.name,
		"status": doc.status,
		"confirmation_message": confirmation_message,
	}
