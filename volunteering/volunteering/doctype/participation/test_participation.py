# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.test_utils import make_test_phone


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = ["Volunteer", "NGO Event"]



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
                "temp_phone": make_test_phone(),
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

    def test_before_insert_links_existing_volunteer_with_leading_zero_phone(self):
        event = self.create_event()
        base_phone = make_test_phone("9876543210")

        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Existing Volunteer",
                "mobile_number": base_phone,
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Temp Volunteer",
                "temp_phone": base_phone.replace("-", "-0", 1),
                "temp_email": f"lead-zero-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(participation.volunteer, volunteer.name)
        self.assertEqual(participation.temp_phone, base_phone)

    def test_before_insert_rejects_all_zero_phone(self):
        event = self.create_event()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "temp_full_name": "All Zero Phone",
                    "temp_phone": "+91-000000",
                }
            ).insert(ignore_permissions=True)
