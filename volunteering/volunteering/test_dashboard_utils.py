# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.dashboard_utils import normalize_dashboard_filters


class IntegrationTestDashboardUtils(IntegrationTestCase):
	def test_normalize_dashboard_filters_returns_list_filters_unchanged(self):
		filters = [["Participation", "event", "=", "EVNT-2026-00001"]]
		self.assertEqual(
			normalize_dashboard_filters(filters, "Participation"),
			filters,
		)

	def test_normalize_dashboard_filters_converts_dict_to_list(self):
		filters = {"event": "EVNT-2026-00003"}
		self.assertEqual(
			normalize_dashboard_filters(filters, "Participation"),
			[["Participation", "event", "=", "EVNT-2026-00003"]],
		)

	def test_normalize_dashboard_filters_handles_json_string(self):
		filters = '{"event": "EVNT-2026-00003"}'
		self.assertEqual(
			normalize_dashboard_filters(filters, "Participation"),
			[["Participation", "event", "=", "EVNT-2026-00003"]],
		)

	def test_normalize_dashboard_filters_returns_empty_for_blank_values(self):
		self.assertEqual(normalize_dashboard_filters(None, "Participation"), [])
		self.assertEqual(normalize_dashboard_filters({}, "Participation"), [])

	def test_dashboard_chart_get_accepts_dict_filters(self):
		if not frappe.db.exists("Dashboard Chart", "Volunteer Referral Leaderboard"):
			self.skipTest("Volunteer Referral Leaderboard chart is not installed")

		from volunteering.volunteering.dashboard_chart import get

		result = get(
			chart_name="Volunteer Referral Leaderboard",
			filters='{"event": "EVNT-2026-00003"}',
			refresh=1,
		)
		self.assertTrue(result is None or "labels" in result)

	def test_kits_distribution_chart_sorts_by_kit_value(self):
		from volunteering.volunteering.dashboard_chart import sort_kits_distribution_by_kit_value

		result = sort_kits_distribution_by_kit_value(
			{
				"labels": ["20", "5", "15", "10"],
				"datasets": [{"name": "Kits Distribution", "values": [30, 11, 3, 11]}],
			}
		)

		self.assertEqual(result["labels"], ["5", "10", "15", "20"])
		self.assertEqual(result["datasets"][0]["values"], [11, 11, 3, 30])
