# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestParticipation(IntegrationTestCase):
    """
    Integration tests for Participation.
    Use this class for testing interactions between multiple components.
    """

    def create_event(self):
        return frappe.get_doc(
            {
                "doctype": "NGO Event",
                "title": f"Event-{frappe.generate_hash(length=8)}",
                "startdate": nowdate(),
                "enddate": nowdate(),
            }
        ).insert(ignore_permissions=True)

    def test_before_insert_links_volunteer_from_temp_phone(self):
        event = self.create_event()

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Test Volunteer",
                "temp_phone": f"99999{frappe.generate_hash(length=5)}",
                "temp_email": f"vol-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertTrue(participation.volunteer)
        self.assertTrue(frappe.db.exists("Volunteer", participation.volunteer))

    def test_before_insert_requires_volunteer_without_phone(self):
        event = self.create_event()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "temp_full_name": "No Phone Volunteer",
                }
            ).insert(ignore_permissions=True)
