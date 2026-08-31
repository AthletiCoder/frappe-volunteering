"""Desk URL helpers.

This site’s Desk lives under ``/desk`` (not ``/app``). Always use these helpers
for DocType links from the SPA / emails / APIs.
"""

from __future__ import annotations

DESK_BASE = "/desk"


def desk_slug(doctype: str) -> str:
	return doctype.lower().replace(" ", "-")


def desk_route(doctype: str, name: str | None = None) -> str:
	slug = desk_slug(doctype)
	if name:
		return f"{DESK_BASE}/{slug}/{name}"
	return f"{DESK_BASE}/{slug}"


def desk_path(*parts: str) -> str:
	"""Join arbitrary desk path segments, e.g. desk_path('query-report', 'X')."""
	cleaned = [str(p).strip("/") for p in parts if p is not None and str(p) != ""]
	return DESK_BASE + ("/" + "/".join(cleaned) if cleaned else "")
