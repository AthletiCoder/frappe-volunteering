import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import CallbackManager

from volunteering.volunteering.hr_policy import policy_on


class UnitTestHRPolicyCache(UnitTestCase):
	def _check_transaction_boundary(self, event, before, after):
		previous = getattr(frappe.local, "sf_hr_policies", None)
		frappe.local.sf_hr_policies = None
		self.addCleanup(setattr, frappe.local, "sf_hr_policies", previous)
		rows = lambda name, days: [frappe._dict(
			name=name, effective_from="2026-01-01", settings=json.dumps({"work_log_days": days}))]
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe.db, "after_commit", CallbackManager()),
			patch.object(frappe.db, "after_rollback", CallbackManager()),
			patch.object(frappe, "get_all", side_effect=[rows(*before), rows(*after)]) as read,
		):
			self.assertEqual(policy_on("2026-11-25")["_revision"], before[0])
			self.assertEqual(policy_on("2026-11-25")["work_log_days"], before[1])
			self.assertEqual(read.call_count, 1)
			getattr(frappe.db, event).run()
			policy = policy_on("2026-11-25")
			self.assertEqual((policy["_revision"], policy["work_log_days"]), after)
			self.assertEqual(read.call_count, 2)

	def test_rollback_drops_a_revision_that_was_not_persisted(self):
		self._check_transaction_boundary("after_rollback", ("rolled-back-policy", 4), ("saved-policy", 2))

	def test_commit_reloads_policy_for_the_next_transaction(self):
		self._check_transaction_boundary("after_commit", ("earlier-policy", 2), ("new-policy", 4))
