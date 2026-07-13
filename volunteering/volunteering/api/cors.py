"""CORS helpers for guest donation APIs called from Vercel."""

from __future__ import annotations

import frappe


DONATION_API_PREFIXES = (
	"/api/method/volunteering.volunteering.api.donations.",
)


def _allowed_origins() -> set[str]:
	try:
		settings = frappe.get_cached_doc("Cashfree Settings")
	except Exception:
		return set()
	raw = (settings.allowed_origins or "").replace("\n", ",")
	return {o.strip() for o in raw.split(",") if o.strip()}


def _origin_allowed(origin: str | None) -> bool:
	if not origin:
		return False
	allowed = _allowed_origins()
	return origin in allowed or "*" in allowed


def handle_donation_cors_preflight():
	"""Hook placeholder — prefer site_config allow_cors for OPTIONS."""
	return


def apply_donation_cors_headers(response=None, request=None):
	if response is None:
		return response
	path = (request.path if request else None) or (frappe.request.path if frappe.request else "")
	if not any(str(path).startswith(p) for p in DONATION_API_PREFIXES):
		return response

	origin = frappe.get_request_header("Origin")
	if _origin_allowed(origin):
		response.headers["Access-Control-Allow-Origin"] = origin
		response.headers["Access-Control-Allow-Credentials"] = "true"
		response.headers["Access-Control-Allow-Headers"] = (
			"Content-Type, Authorization, X-Frappe-CSRF-Token, X-Requested-With"
		)
		response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
		response.headers["Vary"] = "Origin"
	return response
