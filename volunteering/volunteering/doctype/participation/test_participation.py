# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.test_utils import make_test_phone, unique_mobile


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = ["Volunteer", "NGO Event", "Project", "Company", "User"]



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

    def create_volunteer(self, relationship_manager=None, first_name="Test Volunteer"):
        return frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": first_name,
                "mobile_number": make_test_phone(),
                "relationship_manager": relationship_manager,
            }
        ).insert(ignore_permissions=True)

    def create_participation(self, event, volunteer):
        return frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
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

    def test_before_insert_links_legacy_bare_digit_volunteer(self):
        event = self.create_event()
        formatted_phone = unique_mobile("96")
        bare_digits = formatted_phone.replace("+91-", "")

        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Legacy Volunteer",
                "mobile_number": formatted_phone,
            }
        ).insert(ignore_permissions=True)
        frappe.db.set_value(
            "Volunteer",
            volunteer.name,
            "mobile_number",
            bare_digits,
            update_modified=False,
        )

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Returning Volunteer",
                "temp_phone": formatted_phone,
                "temp_email": f"legacy-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(participation.volunteer, volunteer.name)
        self.assertEqual(
            frappe.db.get_value("Volunteer", volunteer.name, "mobile_number"),
            formatted_phone,
        )

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
                "temp_phone": base_phone.replace("+91-", "0"),
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

    def test_kits_delivered_update_without_rating_clears_volunteer_rollup(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Kits Volunteer",
                "mobile_number": unique_mobile("97"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        participation.kits_delivered = 5
        participation.save(ignore_permissions=True)

        volunteer.reload()
        self.assertEqual(volunteer.effective_rating, 0)
        self.assertEqual(volunteer.rating_sample_size, 0)
        self.assertEqual(participation.effective_rating, 0)

    def test_update_participation_field_updates_status(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Grid Volunteer",
                "mobile_number": unique_mobile("98"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        from volunteering.volunteering.doctype.participation.participation import (
            update_participation_field,
        )

        updated = update_participation_field(
            participation.name, "status", "Attended", participation.modified
        )
        self.assertEqual(updated["status"], "Attended")
        self.assertEqual(
            frappe.db.get_value("Participation", participation.name, "status"),
            "Attended",
        )

    def test_update_participation_field_rejects_invalid_field(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Invalid Field Volunteer",
                "mobile_number": unique_mobile("99"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        from volunteering.volunteering.doctype.participation.participation import (
            update_participation_field,
        )

        with self.assertRaises(frappe.ValidationError):
            update_participation_field(
                participation.name, "logging_screenshot", "/files/test.png"
            )

    def test_update_participation_field_rejects_event_change(self):
        event = self.create_event()
        other_event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Event Guard Volunteer",
                "mobile_number": unique_mobile("95"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        from volunteering.volunteering.doctype.participation.participation import (
            update_participation_field,
        )

        with self.assertRaises(frappe.ValidationError):
            update_participation_field(participation.name, "event", other_event.name)

    def test_update_participation_field_requires_rating_when_logged(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Logged Status Volunteer",
                "mobile_number": unique_mobile("94"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        from volunteering.volunteering.doctype.participation.participation import (
            update_participation_field,
        )

        with self.assertRaises(frappe.ValidationError):
            update_participation_field(participation.name, "logging_status", "Logged")

    def test_participation_copies_relationship_manager_on_insert(self):
        event = self.create_event()
        volunteer = self.create_volunteer(relationship_manager=frappe.session.user)
        participation = self.create_participation(event, volunteer)

        self.assertEqual(participation.relationship_manager, frappe.session.user)

    def test_participation_copies_relationship_manager_when_volunteer_changes(self):
        event = self.create_event()
        volunteer_a = self.create_volunteer(
            relationship_manager=frappe.session.user, first_name="Volunteer A"
        )
        volunteer_b = self.create_volunteer(first_name="Volunteer B")
        participation = self.create_participation(event, volunteer_a)

        participation.volunteer = volunteer_b.name
        participation.save(ignore_permissions=True)

        self.assertEqual(participation.relationship_manager, volunteer_b.relationship_manager)

    def test_participation_relationship_manager_empty_when_volunteer_has_none(self):
        event = self.create_event()
        volunteer = self.create_volunteer(first_name="No RM Volunteer")
        participation = self.create_participation(event, volunteer)

        self.assertFalse(participation.relationship_manager)

    def test_update_participation_field_rejects_relationship_manager(self):
        event = self.create_event()
        volunteer = self.create_volunteer(relationship_manager=frappe.session.user)
        participation = self.create_participation(event, volunteer)

        from volunteering.volunteering.doctype.participation.participation import (
            update_participation_field,
        )

        with self.assertRaises(frappe.ValidationError):
            update_participation_field(
                participation.name, "relationship_manager", frappe.session.user
            )

    def test_backfill_participation_relationship_managers(self):
        from volunteering.volunteering.workspace_setup import (
            backfill_participation_relationship_managers,
        )

        event = self.create_event()
        volunteer = self.create_volunteer(relationship_manager=frappe.session.user)
        participation = self.create_participation(event, volunteer)

        frappe.db.set_value(
            "Participation",
            participation.name,
            "relationship_manager",
            None,
            update_modified=False,
        )

        backfill_participation_relationship_managers()

        self.assertEqual(
            frappe.db.get_value("Participation", participation.name, "relationship_manager"),
            frappe.session.user,
        )
