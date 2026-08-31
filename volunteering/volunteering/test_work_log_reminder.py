# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from volunteering.volunteering.api import work_log_reminder as reminder
from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE, ensure_employment_type
from volunteering.volunteering.test_utils import get_or_create_test_employee, get_or_create_test_project


class IntegrationTestWorkLogReminder(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.employee = get_or_create_test_employee()
		self.project = get_or_create_test_project(self.employee)
		ensure_employment_type("Full-time")
		frappe.db.set_value("Employee", self.employee, "employment_type", "Full-time")
		frappe.db.set_single_value("Daily Work Log Settings", "enable_missing_log_reminder", 1)
		frappe.db.set_single_value("Daily Work Log Settings", "backdate_limit_days", 14)
		self.log_date = self._pick_working_day()
		self._cleanup()

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _pick_working_day(self):
		from volunteering.volunteering.attendance_service import get_holiday_info, is_org_weekly_off

		candidate = add_days(nowdate(), -1)
		for _ in range(14):
			if getdate(candidate).weekday() not in (2, 5, 6) and not is_org_weekly_off(candidate):
				if not get_holiday_info(self.employee, candidate):
					return getdate(candidate)
			candidate = add_days(candidate, -1)
		return getdate(add_days(nowdate(), -1))

	def _cleanup(self):
		frappe.db.delete("Daily Work Log", {"employee": self.employee, "date": self.log_date})
		user = frappe.db.get_value("Employee", self.employee, "user_id")
		if user:
			frappe.cache.delete_value(reminder._cache_key(user, self.log_date))

	def _submit_log(self):
		doc = frappe.get_doc(
			{
				"doctype": "Daily Work Log",
				"employee": self.employee,
				"date": self.log_date,
				"items": [
					{
						"project": self.project,
						"task_title": "Reminder test",
						"description": "Enough characters for validation here",
						"time_spent_hours": 6,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _run(self, **kwargs):
		return reminder.send_missing_log_reminders(
			log_date=self.log_date,
			force=True,
			employees=[self.employee],
			**kwargs,
		)

	def test_skips_when_already_logged(self):
		self._submit_log()
		with patch("volunteering.volunteering.api.work_log_reminder.frappe.sendmail") as sendmail:
			result = self._run()
		self.assertEqual(result["sent"], 0)
		self.assertEqual(result["skip_detail"][0]["reason"], "already logged")
		sendmail.assert_not_called()

	def test_skips_unpaid_employee(self):
		ensure_employment_type()
		previous = frappe.db.get_value("Employee", self.employee, "employment_type")
		frappe.db.set_value("Employee", self.employee, "employment_type", UNPAID_EMPLOYMENT_TYPE)
		try:
			with patch("volunteering.volunteering.api.work_log_reminder.frappe.sendmail") as sendmail:
				result = self._run()
			self.assertEqual(result["sent"], 0)
			self.assertEqual(result["skip_detail"][0]["reason"], "unpaid")
			sendmail.assert_not_called()
		finally:
			frappe.db.set_value("Employee", self.employee, "employment_type", previous)

	def test_sends_when_missing_log(self):
		user = frappe.db.get_value("Employee", self.employee, "user_id")
		if user and frappe.db.has_column("User", reminder.OPT_IN_FIELD):
			frappe.db.set_value("User", user, reminder.OPT_IN_FIELD, 1)
			frappe.cache.delete_value(reminder._cache_key(user, self.log_date))

		with patch("volunteering.volunteering.api.work_log_reminder.frappe.sendmail") as sendmail:
			result = self._run()

		self.assertEqual(result["sent"], 1)
		self.assertEqual(result["recipients"][0]["employee"], self.employee)
		self.assertTrue(sendmail.called)

	def test_opt_out_skips_send(self):
		user = frappe.db.get_value("Employee", self.employee, "user_id")
		if not user or not frappe.db.has_column("User", reminder.OPT_IN_FIELD):
			self.skipTest("User opt-in field not installed")
		frappe.db.set_value("User", user, reminder.OPT_IN_FIELD, 0)
		frappe.cache.delete_value(reminder._cache_key(user, self.log_date))
		try:
			with patch("volunteering.volunteering.api.work_log_reminder.frappe.sendmail") as sendmail:
				result = self._run()
			self.assertEqual(result["sent"], 0)
			self.assertEqual(result["skip_detail"][0]["reason"], "opted out")
			sendmail.assert_not_called()
		finally:
			frappe.db.set_value("User", user, reminder.OPT_IN_FIELD, 1)

	def test_hourly_gate_skips_wrong_hour(self):
		with patch(
			"volunteering.volunteering.api.work_log_reminder.get_datetime",
			return_value=datetime(2026, 8, 31, 3, 0, 0),
		):
			frappe.db.set_single_value("Daily Work Log Settings", "missing_log_reminder_hour", 9)
			result = reminder.run_morning_missing_log_reminders(force=False)
		self.assertTrue(result.get("skipped"))
		self.assertEqual(result.get("reason"), "wrong hour")
