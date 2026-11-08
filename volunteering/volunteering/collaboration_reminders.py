"""Permission-checked schedules consumed by native Android local reminders. No email."""
from datetime import datetime, time, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, getdate, get_system_timezone, now_datetime

from volunteering.volunteering import collaboration as c

MORNING = "09:00"


def events_for(item, user, now, timezone):
	"""One reminder per item/day, plus a distinct deadline if outside its action window."""
	if item.status not in c.OPEN or item.item_kind not in {"Task", "Tracker"}:
		return []
	config = c._json(item.item_data, {})
	responsible = {item.assignee, item.owner}
	if item.item_kind == "Tracker" and config.get("assignment_mode") == "Stages":
		stages = config.get("stages", [])
		current = next((s for s in stages if s["key"] == config.get("stage")), stages[0] if stages else {})
		responsible = {item.owner, current.get("assignee")}
	subtasks = [row for row in config.get("subtasks", []) if row.get("status") != "Completed" and (row.get("assignee") or item.assignee) == user]
	responsible.update(row.get("assignee") for row in subtasks)
	if user not in responsible and c._share_level(item, user) != "Update":
		return []
	start = item.from_date if item.item_kind == "Task" else config.get("attention_date")
	end = item.until_date if item.item_kind == "Task" else config.get("attention_until")
	today = now.date()
	horizon = today + timedelta(days=30)
	days = set()
	if start:
		first, last = max(getdate(start), today), min(getdate(end or start), horizon)
		while first <= last:
			days.add(first)
			first += timedelta(days=1)
	if item.deadline and today <= getdate(item.deadline) <= horizon:
		days.add(getdate(item.deadline))
	for row in subtasks:
		if row.get("deadline") and today <= getdate(row["deadline"]) <= horizon:
			days.add(getdate(row["deadline"]))
	clock = time.fromisoformat(config.get("reminder_time") or MORNING)
	zone = ZoneInfo(timezone)
	return [{"key": sha256(f"{item.name}:{day}:{clock}".encode()).hexdigest(), "item": item.name,
		"space": item.space, "kind": item.item_kind, "title": item.title,
		"timestamp_ms": int(datetime.combine(day, clock, zone).timestamp() * 1000),
		"scheduled_at": datetime.combine(day, clock, zone).isoformat()}
		for day in sorted(days) if not item.snoozed_until or day >= getdate(item.snoozed_until)]


@frappe.whitelist(methods=["POST"])
def get_reminders():
	from volunteering.volunteering.collaboration_access import require_chat_access
	user = require_chat_access("app")
	work = c.get_my_work()
	zone = get_system_timezone()
	now = now_datetime()
	events = []
	for row in work["open_progress"]:
		doc, room, root, _level = c._read_item(row["name"])
		if not room.archived and not root.archived:
			events.extend(events_for(doc, user, now, zone))
	return {"user": user, "timezone": zone, "morning_time": MORNING, "reminders": events,
		"generated_at": str(now), "has_more": work["has_more"]}
