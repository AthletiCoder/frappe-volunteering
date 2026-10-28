"""Keep Frappe's best-effort activity metadata out of the login transaction.

Frappe v16 updates last_login/last_ip/last_active after inserting a session.
MariaDB can abort the whole transaction on a snapshot conflict, invalidating
the savepoint in that helper and turning an otherwise valid login into HTTP 500.
Only this non-critical helper runs on a separate connection. Authentication,
session persistence, permissions and application transactions remain standard.
"""

from functools import wraps

import frappe
from frappe.database import get_db


def install_session_metadata_isolation(login_manager=None):
	"""Install once per worker, before new-session or resumed-session persistence."""
	import frappe.sessions

	original = getattr(frappe.sessions, "update_user_metadata", None)
	if not callable(original) or getattr(original, "_sevamrita_metadata_isolation", False):
		return

	@wraps(original)
	def isolated(user, **values):
		if "volunteering" not in frappe.get_installed_apps() or frappe.db.db_type == "sqlite":
			return original(user, **values)
		if not user or user == "Guest" or not any(
			values.get(field) is not None for field in ("last_login", "last_ip", "last_active")
		):
			return
		return _update_metadata(original, user, values)

	isolated._sevamrita_metadata_isolation = True
	frappe.sessions.update_user_metadata = isolated


def _update_metadata(original, user, values):
	request_db = frappe.local.db
	metadata_db = None
	try:
		metadata_db = get_db(
			socket=request_db.socket,
			host=request_db.host,
			user=request_db.user,
			password=request_db.password,
			port=request_db.port,
			cur_db_name=request_db.cur_db_name,
		)
		# frappe.local is request/thread-local. Reuse the framework helper and its
		# notifications without committing or rolling back the caller's work.
		frappe.local.db = metadata_db
		# Another request (or the login's own hook) may already hold this row.
		# Never wait on it from a second connection and stall session creation.
		metadata_db.get_value("User", user, "name", for_update=True, wait=False)
		original(user, **values)
		metadata_db.commit()
	except Exception:
		# Activity metadata is explicitly best-effort in Frappe; record failures
		# without hiding errors in authentication or any application operation.
		frappe.logger("session_metadata").warning(
			"Could not refresh non-critical session activity metadata", exc_info=True
		)
		if metadata_db is not None:
			try:
				metadata_db.rollback()
			except Exception:
				pass  # A deadlock may already have discarded this isolated transaction.
	finally:
		frappe.local.db = request_db
		if metadata_db is not None:
			try:
				metadata_db.close()
			except Exception:
				frappe.logger("session_metadata").warning("Could not close activity connection", exc_info=True)
