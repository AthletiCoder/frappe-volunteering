"""Leave balances use HRMS allocations and signed Leave Adjustment ledger entries."""
import calendar

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cstr, flt, getdate, nowdate

from volunteering.volunteering.hr_policy import policy_on, leave_year, applies_to_employee, require_policy_manager, reason_text

PAID = "Privilege Leave"
COMP = "Compensatory Leave"
LWP = "Leave Without Pay"


def sync_leave_masters():
	policy = policy_on()
	if policy.get("_revision"):
		frappe.db.set_single_value("Payroll Settings", "payroll_based_on", "Attendance" if policy["attendance_based_payroll"] else "Leave")
	for name, values in {
		PAID: {"is_earned_leave": 1, "earned_leave_frequency": "Monthly", "allocate_on_day": "First Day",
			"rounding": "0.25", "is_carry_forward": 1, "maximum_carry_forwarded_leaves": policy["carry_forward_days"],
			"max_leaves_allowed": 0, "allow_negative": policy["allow_negative_paid_leave"], "include_holiday": 0},
		COMP: {"is_compensatory": 1, "is_carry_forward": 1, "is_earned_leave": 0,
			"maximum_carry_forwarded_leaves": 0, "max_leaves_allowed": 0, "allow_negative": 0, "include_holiday": 0},
		LWP: {"is_lwp": 1, "include_holiday": 0},
	}.items():
		doc = frappe.get_doc("Leave Type", name) if frappe.db.exists("Leave Type", name) else frappe.new_doc("Leave Type")
		if not doc.is_new() and all(doc.get(key) == value for key, value in values.items()):
			continue
		doc.leave_type_name = name
		doc.update(values)
		doc.save(ignore_permissions=True)
	# Older HRMS allocations retain their original earned-leave schedules and
	# annual caps. HR explicitly adopts their verified balance before the managed
	# calendar-year schedule takes over; editing one part alone could over-credit
	# leave or make the old annual cap reject later monthly credits.


def lock_employee(employee):
	frappe.db.get_value("Employee", employee, "name", for_update=True)


def salary_processed(employee, start, end):
	return frappe.db.exists("Salary Slip", {"employee": employee, "docstatus": 1,
		"start_date": ["<=", end], "end_date": [">=", start]})


def require_unprocessed_salary(employee, start, end):
	if salary_processed(employee, start, end):
		frappe.throw(_("Payroll is already submitted for these dates. Arrange a payroll correction before changing their attendance or leave."))


def current_allocation(employee, leave_type, day=None):
	day = getdate(day or nowdate())
	return frappe.db.get_value("Leave Allocation", {"employee": employee, "leave_type": leave_type, "docstatus": 1,
		"from_date": ["<=", day], "to_date": [">=", day]}, ["name", "from_date", "to_date", "sf_managed_policy"], as_dict=True)


def ensure_allocation(employee, leave_type=PAID, day=None, start_override=None):
	day = getdate(day or nowdate())
	existing = current_allocation(employee, leave_type, day)
	if existing: return frappe.get_doc("Leave Allocation", existing.name)
	policy = policy_on(day); start, end = leave_year(day, policy)
	joining = getdate(frappe.db.get_value("Employee", employee, "date_of_joining"))
	start = max(start, joining, getdate(start_override)) if start_override else max(start, joining)
	if start > day: frappe.throw(_("Leave cannot be allocated before the employee joins."))
	# An overlapping legacy allocation is never silently shortened or re-granted.
	overlap = frappe.db.exists("Leave Allocation", {"employee": employee, "leave_type": leave_type, "docstatus": 1,
		"from_date": ["<=", end], "to_date": [">=", start]})
	if overlap:
		frappe.throw(_("An older leave allocation overlaps this leave year. HR must review and adopt its balance first."))
	doc = frappe.get_doc({"doctype": "Leave Allocation", "employee": employee, "leave_type": leave_type,
		"from_date": start, "to_date": end, "new_leaves_allocated": 0,
		# A next-year request must not carry/expire this year's balance early.
		# The managed year-opening posting below performs carry-forward once due.
		"carry_forward": 0, "sf_managed_policy": 1, "sf_policy_revision": policy.get("_revision")})
	doc.insert(ignore_permissions=True); doc.submit()
	return doc


def post_leave(employee, leave_type, days, day, reason, source, source_name, key):
	"""Exactly-once ledger posting; the caller holds the employee transaction lock."""
	name = frappe.db.get_value("HR Leave Posting", {"unique_key": key}, "name")
	if name:
		posted = frappe.get_doc("HR Leave Posting", name)
		if source != "Monthly accrual" and (posted.employee != employee or posted.leave_type != leave_type or flt(posted.days) != flt(days) or posted.reason != reason):
			frappe.throw(_("This request reference was used for a different leave adjustment."))
		return posted
	allocation = ensure_allocation(employee, leave_type, day)
	if source != "Carry forward": _carry_forward(employee, leave_type, allocation, getdate(day))
	posting = frappe.get_doc({"doctype": "HR Leave Posting", "employee": employee, "leave_type": leave_type,
		"posting_date": day, "days": days, "reason": reason, "source": source, "source_name": source_name,
		"unique_key": key, "policy_revision": policy_on(day).get("_revision")})
	posting.flags.policy_posting = True; posting.insert(ignore_permissions=True)
	adjustment = frappe.get_doc({"doctype": "Leave Adjustment", "employee": employee, "leave_type": leave_type,
		"leave_allocation": allocation.name, "adjustment_type": "Allocate" if days > 0 else "Reduce",
		"leaves_to_adjust": abs(days), "posting_date": day, "from_date": day, "to_date": allocation.to_date,
		"allocated_leaves": allocation.total_leaves_allocated, "reason_for_adjustment": reason,
		"sf_policy_posting": posting.name})
	adjustment.flags.hr_policy_posting = True
	adjustment.insert(ignore_permissions=True); adjustment.submit()
	posting.db_set("adjustment", adjustment.name)
	return posting


def _carry_forward(employee, leave_type, allocation, day):
	start, end = leave_year(day)
	if getdate(allocation.from_date) != start or day > getdate(nowdate()): return
	key = f"carry:{employee}:{leave_type}:{start}"
	if frappe.db.exists("HR Leave Posting", {"unique_key": key}): return
	previous = frappe.db.get_value("Leave Allocation", {"employee": employee, "leave_type": leave_type,
		"docstatus": 1, "to_date": ["<", start]}, ["name", "from_date", "to_date"], as_dict=True, order_by="to_date desc")
	if not previous: return
	if leave_type == PAID:
		from hrms.hr.doctype.leave_allocation.leave_allocation import get_unused_leaves
		amount = min(flt(get_unused_leaves(employee, leave_type, previous.from_date, previous.to_date)), policy_on(start)["carry_forward_days"])
	else:
		amount = 0
		for credit in frappe.get_all("Staff Time Request", filters={"employee": employee, "request_type": "Compensatory Credit",
			"status": "Approved", "from_date": ["<", start], "valid_until": [">=", start]}, fields=["name", "credit_days", "expired_days"]):
			used = sum(row.days for row in frappe.get_all("Compensatory Leave Use", filters={"credit": credit.name, "leave_date": ["<", start]}, fields=["days"]))
			amount += max(0, flt(credit.credit_days)-flt(credit.expired_days)-used)
	if amount:
		post_leave(employee, leave_type, amount, start, "Leave year opening carry-forward", "Carry forward", previous.name, key)
	else:
		posting = frappe.get_doc({"doctype": "HR Leave Posting", "employee": employee, "leave_type": leave_type, "posting_date": start,
			"days": 0, "reason": "No unused leave carried forward", "source": "Carry forward", "source_name": previous.name, "unique_key": key})
		posting.flags.policy_posting = True; posting.insert(ignore_permissions=True)


def paid_balance(employee, day=None):
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
	return flt(get_leave_balance_on(employee, PAID, getdate(day or nowdate())))


def credit_month(employee, credit_date):
	credit_date = getdate(credit_date); lock_employee(employee)
	if not applies_to_employee(employee, credit_date): return None
	policy = policy_on(credit_date)
	allocation = ensure_allocation(employee, PAID, credit_date)
	if not allocation.get("sf_managed_policy"): return None  # Legacy credits remain under their original schedule.
	joining = getdate(frappe.db.get_value("Employee", employee, "date_of_joining"))
	if credit_date < joining: return None
	amount = flt(policy["monthly_leave"])
	if credit_date.month == joining.month and credit_date.year == joining.year:
		length = calendar.monthrange(joining.year, joining.month)[1]
		amount = round(amount * (length - joining.day + 1) / length * 4) / 4
	if not amount: return None
	return post_leave(employee, PAID, amount, credit_date, "Monthly earned leave", "Monthly accrual", str(credit_date), f"monthly:{employee}:{credit_date:%Y-%m}")


def ensure_current_balance(employee, day=None):
	"""Only credit elapsed months for new managed allocations, never future months."""
	day = getdate(day or nowdate()); lock_employee(employee)
	if not applies_to_employee(employee, day): return
	allocation = ensure_allocation(employee, PAID, day)
	if not allocation.get("sf_managed_policy"): return
	_carry_forward(employee, PAID, allocation, day)
	comp = current_allocation(employee, COMP, day)
	if comp: _carry_forward(employee, COMP, frappe.get_doc("Leave Allocation", comp.name), day)
	posted_months = set(frappe.get_all("HR Leave Posting", filters={"employee": employee, "source": "Monthly accrual"}, pluck="unique_key"))
	first = getdate(allocation.from_date)
	# A mid-month cutover includes that month's entitlement in its verified opening.
	month = first.replace(day=1)
	if first.day > 1:
		joining = getdate(frappe.db.get_value("Employee", employee, "date_of_joining"))
		if first == joining:
			credit_month(employee, first)
		month = getdate(add_months(month, 1))
	while month <= day:
		if f"monthly:{employee}:{month:%Y-%m}" not in posted_months: credit_month(employee, month)
		month = getdate(add_months(month, 1))


@frappe.whitelist(methods=["POST"])
def preview_leave_adoption(employee):
	require_policy_manager()
	allocation = current_allocation(employee, PAID)
	if allocation: allocation.sf_managed_policy = bool(allocation.sf_managed_policy)
	start, end = leave_year()
	return {"employee": employee, "allocation": allocation, "today": nowdate(), "leave_year_from": start, "leave_year_to": end,
		"needs_adoption": bool(allocation and (not allocation.sf_managed_policy or getdate(allocation.to_date) != end)),
		"balance": paid_balance(employee), "has_future_leave": bool(frappe.db.exists("Leave Application", {
			"employee": employee, "docstatus": ["<", 2], "status": ["in", ["Open", "Approved"]], "to_date": [">=", nowdate()]}))}


@frappe.whitelist(methods=["POST"])
def adopt_leave_year(employee, opening_balance, reason, expected_allocation=None, request_key=None):
	require_policy_manager(); reason = reason_text(reason); lock_employee(employee)
	if not request_key: frappe.throw(_("A request reference is required."))
	key = f"adoption:{employee}:{request_key}"
	if frappe.db.exists("HR Leave Posting", {"unique_key": key}): return preview_leave_adoption(employee)
	preview = preview_leave_adoption(employee)
	allocation = preview["allocation"]
	if not allocation or allocation.name != expected_allocation:
		frappe.throw(_("The allocation changed. Preview it again."))
	if not preview["needs_adoption"]: frappe.throw(_("This employee already uses the configured leave year."))
	if preview["has_future_leave"]:
		frappe.throw(_("Resolve open/future approved leave before changing this employee's leave year."))
	if frappe.db.exists("Leave Adjustment", {"leave_allocation": allocation.name, "docstatus": 1, "posting_date": [">=", nowdate()]}):
		frappe.throw(_("This allocation has a current or future adjustment. Review it before adopting the leave year."))
	require_unprocessed_salary(employee, nowdate(), preview["leave_year_to"])
	try: balance = float(opening_balance)
	except (ValueError, TypeError): frappe.throw(_("Enter the verified opening balance."))
	if not (-366 <= balance <= 366): frappe.throw(_("Enter a finite opening balance between -366 and 366."))
	cutoff = getdate(add_days(nowdate(), -1))
	if getdate(allocation.from_date) > cutoff: frappe.throw(_("Use a balance adjustment for an allocation created today."))
	frappe.db.set_value("Leave Allocation", allocation.name, "to_date", cutoff)
	# Adjustments attached to the old allocation must also end at the cutover,
	# otherwise both their credit and the verified opening remain spendable.
	frappe.db.sql("""UPDATE `tabLeave Ledger Entry` SET to_date=%s
		WHERE to_date>%s AND (transaction_type='Leave Allocation' AND transaction_name=%s
		OR transaction_type='Leave Adjustment' AND transaction_name IN
		(SELECT name FROM `tabLeave Adjustment` WHERE leave_allocation=%s AND docstatus=1))""",
		(cutoff, cutoff, allocation.name, allocation.name))
	frappe.db.sql("DELETE FROM `tabEarned Leave Schedule` WHERE parent=%s AND is_allocated=0 AND allocation_date>%s", (allocation.name, cutoff))
	frappe.get_doc("Leave Allocation", allocation.name).add_comment("Info", _("HR calendar-year adoption by {0}: {1}").format(frappe.session.user, frappe.utils.escape_html(reason)))
	new = ensure_allocation(employee, PAID, nowdate(), start_override=nowdate())
	if balance:
		post_leave(employee, PAID, balance, nowdate(), reason, "Year adoption", allocation.name, key)
	else:
		# A zero opening still needs a durable receipt for a retry.
		posting = frappe.get_doc({"doctype": "HR Leave Posting", "employee": employee, "leave_type": PAID,
			"posting_date": nowdate(), "days": 0, "reason": reason, "source": "Year adoption", "source_name": allocation.name, "unique_key": key})
		posting.flags.policy_posting = True; posting.insert(ignore_permissions=True)
	return preview_leave_adoption(employee)


@frappe.whitelist(methods=["POST"])
def adjust_leave_balance(employee, days, reason, request_key):
	require_policy_manager(); reason = reason_text(reason); lock_employee(employee)
	ensure_current_balance(employee)
	amount = flt(days)
	if not amount or not -120 <= amount <= 120: frappe.throw(_("Enter a non-zero adjustment between -120 and 120 days."))
	if amount * 4 != round(amount * 4): frappe.throw(_("Use quarter-day increments for a leave adjustment."))
	if not request_key or len(cstr(request_key)) > 100: frappe.throw(_("A valid request reference is required."))
	post_leave(employee, PAID, amount, nowdate(), reason, "HR adjustment", frappe.session.user, f"hr:{employee}:{request_key}")
	return {"balance": paid_balance(employee)}


def daily_leave_jobs():
	sync_leave_masters()
	for employee in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
		frappe.enqueue("volunteering.volunteering.hr_leave_balances.process_employee_leave", employee=employee, enqueue_after_commit=True)


def process_employee_leave(employee):
	# Separate transactions prevent a lock conflict for one person from rolling
	# back another person's accrual, or retaining locks across the entire staff.
	from volunteering.volunteering.expense_claim_requests import _retry_snapshot_conflict
	def process():
		ensure_current_balance(employee)
		from volunteering.volunteering.time_leave_portal import expire_compensatory_credits
		expire_compensatory_credits(employee)
	return _retry_snapshot_conflict(process)


def reconcile_leave_carry(doc, method=None):
	"""Late approval/cancellation adjusts the next year's carry with a new entry."""
	if doc.leave_type != PAID or not doc.get("sf_policy_revision"): return
	if doc.status != "Approved" and doc.docstatus != 2: return
	lock_employee(doc.employee)
	for carry in frappe.get_all("HR Leave Posting", filters={"employee": doc.employee, "leave_type": PAID,
		"source": "Carry forward", "posting_date": ["between", [add_days(doc.to_date, 1), nowdate()]]},
		fields=["name", "source_name", "days", "posting_date"]):
		previous = frappe.db.get_value("Leave Allocation", carry.source_name, ["from_date", "to_date"], as_dict=True)
		if not previous or not (getdate(previous.from_date) <= getdate(doc.from_date) <= getdate(previous.to_date)): continue
		from hrms.hr.doctype.leave_allocation.leave_allocation import get_unused_leaves
		target = min(flt(get_unused_leaves(doc.employee, PAID, previous.from_date, previous.to_date)), policy_on(carry.posting_date)["carry_forward_days"])
		already = flt(carry.days) + sum(row.days for row in frappe.get_all("HR Leave Posting", filters={"source": "Carry correction", "source_name": carry.name}, fields=["days"]))
		difference = flt(target-already)
		if difference:
			import hashlib
			key = hashlib.sha256(f"carry-correction:{carry.name}:{doc.name}:{doc.modified}:{doc.docstatus}".encode()).hexdigest()
			post_leave(doc.employee, PAID, difference, nowdate(), f"Carry-forward corrected after leave {doc.name}: {doc.status}", "Carry correction", carry.name, key)
