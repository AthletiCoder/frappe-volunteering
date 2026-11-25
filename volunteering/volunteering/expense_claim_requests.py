"""Transaction-backed receipt for a claim submission, shared by web and native clients.

No payload, receipt bytes or signatures are retained here. The result is committed
in the same transaction as every claim/file/invoice created by the operation.
"""
import hashlib
import json
import re
import time

import frappe
from frappe import _
from frappe.utils import cstr

OPERATIONS = {"single", "multiple", "generated"}


def _key(employee, request_key):
	key = cstr(request_key).strip()
	if not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", key):
		frappe.throw(_("Invalid submission reference. Reopen the expense form."))
	return hashlib.sha256(f"{employee}:{key}".encode()).hexdigest()


def _canonical(value):
	if isinstance(value, dict):
		# Signature proofs are short-lived server attestations of the same data.
		return {key: _canonical(item) for key, item in value.items()
			if key not in {"volunteer_signature_proof", "vendor_signature_proof"}}
	if isinstance(value, list):
		return [_canonical(item) for item in value]
	return value


def _lock(employee):
	# Serializes creation and recovery; a concurrent recovery waits for the first
	# request to commit/roll back instead of returning a misleading 'not found'.
	frappe.db.get_value("Employee", employee, "name", for_update=True)


def _retry_snapshot_conflict(operation):
	# MariaDB snapshot isolation can abort a waiting transaction when the first
	# request commits a row absent from the waiter's original read view (1020).
	# Restart the whole operation with a fresh view, including rollback hooks for
	# private files. Never discard writes belonging to a caller's earlier work.
	can_restart = frappe.db.transaction_writes == 0
	for attempt in range(3):
		try:
			return operation()
		except frappe.QueryDeadlockError:
			if not can_restart or attempt == 2:
				raise
			frappe.db.rollback()


def submit_once(operation, request_key, payload, create):
	return _retry_snapshot_conflict(lambda: _submit_once(operation, request_key, payload, create))


def _submit_once(operation, request_key, payload, create):
	from volunteering.volunteering.expense_claim_portal import _require_employee

	employee = _require_employee()
	if operation not in OPERATIONS:
		frappe.throw(_("Invalid expense operation."))
	# Compatibility for older deployed clients; updated clients always send a key.
	if not request_key:
		return create()
	name = _key(employee, request_key)
	fingerprint = hashlib.sha256(json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
	_lock(employee)
	stored = frappe.db.get_value("Expense Claim Request", name, ["employee", "operation", "fingerprint", "result"], as_dict=True, for_update=True)
	if stored:
		if stored.employee != employee or stored.operation != operation or stored.fingerprint != fingerprint:
			frappe.throw(_("This submission reference was already used for different details. Check the saved claim before starting another."))
		return frappe.parse_json(stored.result)
	started = time.monotonic()
	savepoint = "claim_request_" + frappe.generate_hash(length=10)
	frappe.db.savepoint(savepoint)
	try:
		result = create()
		frappe.get_doc({"doctype": "Expense Claim Request", "name": name, "employee": employee,
			"operation": operation, "fingerprint": fingerprint, "result": json.dumps(result, default=str)}).insert(ignore_permissions=True, set_name=name)
	except frappe.QueryDeadlockError:
		# InnoDB has already rolled back this transaction, including savepoints.
		raise
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise
	elapsed = round((time.monotonic() - started) * 1000)
	if elapsed > 3000:
		frappe.logger("expense_submissions").info({"operation": operation, "processing_ms": elapsed})
	return result


@frappe.whitelist(methods=["POST"])
def get_expense_submission_status(request_key):
	return _retry_snapshot_conflict(lambda: _submission_status(request_key))


def _submission_status(request_key):
	from volunteering.volunteering.expense_claim_portal import _require_employee

	employee = _require_employee()
	name = _key(employee, request_key)
	_lock(employee)
	stored = frappe.db.get_value("Expense Claim Request", name, ["employee", "result"], as_dict=True, for_update=True)
	if not stored or stored.employee != employee:
		return {"found": False}
	return {"found": True, "result": frappe.parse_json(stored.result)}
