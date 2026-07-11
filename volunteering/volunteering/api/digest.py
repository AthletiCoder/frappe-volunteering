"""Daily donation digest email for Accounts / Admins."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, format_datetime, get_datetime, nowdate


def send_daily_donation_digest():
	settings = frappe.get_single("Cashfree Settings")
	if not settings.enable_daily_digest:
		return {"skipped": True}

	recipients = _digest_recipients(settings)
	if not recipients:
		return {"skipped": True, "reason": "no recipients"}

	yesterday = add_days(nowdate(), -1)
	start = get_datetime(f"{yesterday} 00:00:00")
	end = get_datetime(f"{yesterday} 23:59:59")

	rows = frappe.get_all(
		"Donation",
		filters={"creation": ["between", [start, end]]},
		fields=["name", "status", "amount", "full_name", "want_80g"],
	)

	success = [r for r in rows if r.status == "Success"]
	failed = [r for r in rows if r.status == "Failed"]
	pending = frappe.get_all(
		"Donation",
		filters={"status": ["in", ["Initiated", "Pending"]]},
		fields=["name", "amount", "modified"],
		limit=20,
		order_by="modified asc",
	)

	total_success = sum(flt(r.amount) for r in success)
	subject = f"Donation digest {yesterday}: ₹{total_success:,.0f} ({len(success)} success)"

	lines = [
		f"<p><b>Date:</b> {yesterday}</p>",
		f"<p><b>Successful:</b> {len(success)} — ₹{total_success:,.2f}</p>",
		f"<p><b>Failed:</b> {len(failed)}</p>",
		f"<p><b>Created that day (all statuses):</b> {len(rows)}</p>",
		f"<p><b>Currently stuck Pending/Initiated:</b> {len(pending)}</p>",
	]
	if pending:
		lines.append("<ul>")
		for p in pending[:10]:
			lines.append(
				f"<li>{p.name} — ₹{flt(p.amount):,.0f} (modified {format_datetime(p.modified)})</li>"
			)
		lines.append("</ul>")

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message="\n".join(lines),
		delayed=True,
	)
	return {
		"recipients": recipients,
		"success_count": len(success),
		"total_success": total_success,
		"failed_count": len(failed),
		"pending_stuck": len(pending),
	}


def _digest_recipients(settings) -> list[str]:
	raw = (settings.digest_recipients or "").replace("\n", ",")
	emails = [e.strip() for e in raw.split(",") if e.strip() and "@" in e]
	if emails:
		return sorted(set(emails))

	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["Accounts Manager", "System Manager"]], "parenttype": "User"},
		fields=["parent"],
		distinct=True,
	)
	result = []
	for row in users:
		user = row.parent
		if user in ("Administrator", "Guest"):
			continue
		enabled = frappe.db.get_value("User", user, ["enabled", "email"], as_dict=True)
		if enabled and enabled.enabled and enabled.email:
			result.append(enabled.email)
	return sorted(set(result))
