# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate
from frappe.tests import IntegrationTestCase
from volunteering.volunteering.report.generic_event_participation_report.generic_event_participation_report import (
    execute,
)


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestNGOEvent(IntegrationTestCase):
    """
    Integration tests for NGOEvent.
    Use this class for testing interactions between multiple components.
    """

    def create_event(self):
        return frappe.get_doc(
            {
                "doctype": "NGO Event",
                "title": f"ReportEvent-{frappe.generate_hash(length=8)}",
                "startdate": nowdate(),
                "enddate": nowdate(),
            }
        ).insert(ignore_permissions=True)

    def create_volunteer(self):
        return frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Report Volunteer",
                "mobile_number": f"88888{frappe.generate_hash(length=5)}",
                "email": f"report-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

    def test_report_maps_dynamic_question_answers(self):
        event = self.create_event()
        volunteer = self.create_volunteer()

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        frappe.get_doc(
            {
                "doctype": "Participation Extra Detail",
                "parent": participation.name,
                "parenttype": "Participation",
                "parentfield": "extra_details",
                "question": "Kits to Distribute",
                "answer": "10",
            }
        ).insert(ignore_permissions=True)

        columns, data = execute({"event": event.name})
        self.assertTrue(any(col.get("fieldname") == "kits_to_distribute" for col in columns))
        self.assertTrue(any(row.get("kits_to_distribute") == "10" for row in data))
