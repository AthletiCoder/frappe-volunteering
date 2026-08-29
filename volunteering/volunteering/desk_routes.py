"""Desk /app URL helpers (hyphenated slugs, not frappe.scrub underscores)."""


def desk_route(doctype: str, name: str | None = None) -> str:
	slug = doctype.lower().replace(" ", "-")
	if name:
		return f"/app/{slug}/{name}"
	return f"/app/{slug}"
