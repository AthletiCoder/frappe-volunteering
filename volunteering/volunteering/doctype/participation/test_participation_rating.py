# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, nowdate
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.doctype.participation.participation import (
    _get_rm_rating_stars,
    update_volunteer_rating_rollup,
)
from volunteering.volunteering.test_utils import unique_mobile


class TestParticipationRatingHelpers(UnitTestCase):
    def test_rm_rating_fraction_to_stars(self):
        self.assertEqual(_get_rm_rating_stars(0.8), 4.0)
        self.assertEqual(_get_rm_rating_stars(1.0), 5.0)
        self.assertEqual(_get_rm_rating_stars(0), 0)

    def test_rm_rating_legacy_star_values(self):
        self.assertEqual(_get_rm_rating_stars(4), 4.0)
        self.assertEqual(_get_rm_rating_stars(6), 5.0)


class IntegrationTestParticipationRating(IntegrationTestCase):
    def create_event(self, title_suffix="", end_offset=0):
        return frappe.get_doc(
            {
                "doctype": "NGO Event",
                "title": f"RatingEvent-{title_suffix or frappe.generate_hash(length=8)}",
                "startdate": nowdate(),
                "enddate": add_days(nowdate(), end_offset),
            }
        ).insert(ignore_permissions=True)

    def create_volunteer(self, relationship_manager=None):
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Rating Volunteer",
                "mobile_number": unique_mobile("96"),
                "relationship_manager": relationship_manager,
            }
        ).insert(ignore_permissions=True)
        return volunteer

    def create_rated_participation(
        self,
        volunteer,
        event,
        rm_rating=0.8,
        kits_delivered=10,
        hours_logged=5,
    ):
        return frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
                "logging_status": "Logged",
                "kits_delivered": kits_delivered,
                "hours_logged": hours_logged,
                "rm_rating": rm_rating,
            }
        ).insert(ignore_permissions=True)

    def test_effective_rating_matches_expected_hours(self):
        event = self.create_event()
        volunteer = self.create_volunteer()
        participation = self.create_rated_participation(
            volunteer, event, rm_rating=0.8, kits_delivered=10, hours_logged=5
        )

        self.assertEqual(participation.expected_hours, 5)
        self.assertEqual(participation.delta_hours, 0)
        self.assertEqual(participation.effective_rating, 4)

    def test_effective_rating_adjusts_for_hours_delta(self):
        event = self.create_event()
        volunteer = self.create_volunteer()
        participation = self.create_rated_participation(
            volunteer, event, rm_rating=0.8, kits_delivered=10, hours_logged=2.5
        )

        self.assertEqual(participation.delta_hours, -2.5)
        self.assertEqual(participation.effective_rating, 3.6)

    def test_insert_updates_volunteer_rollup(self):
        event = self.create_event()
        volunteer = self.create_volunteer()
        self.create_rated_participation(volunteer, event)

        volunteer.reload()
        self.assertEqual(volunteer.effective_rating, 4)
        self.assertEqual(volunteer.rating_sample_size, 1)

    def test_delete_participation_recalculates_volunteer_rollup(self):
        event = self.create_event()
        volunteer = self.create_volunteer()
        participation = self.create_rated_participation(volunteer, event)

        volunteer.reload()
        self.assertEqual(volunteer.effective_rating, 4)

        participation.delete(ignore_permissions=True)
        volunteer.reload()
        self.assertEqual(volunteer.effective_rating, 0)
        self.assertEqual(volunteer.rating_sample_size, 0)

    def test_volunteer_change_updates_both_rollups(self):
        event = self.create_event()
        volunteer_a = self.create_volunteer()
        volunteer_b = self.create_volunteer()
        participation = self.create_rated_participation(volunteer_a, event, rm_rating=1.0)

        volunteer_a.reload()
        self.assertEqual(volunteer_a.effective_rating, 5)

        participation.volunteer = volunteer_b.name
        participation.save(ignore_permissions=True)

        volunteer_a.reload()
        volunteer_b.reload()
        self.assertEqual(volunteer_a.effective_rating, 0)
        self.assertEqual(volunteer_b.effective_rating, 5)

    def test_volunteer_rollup_uses_recent_event_weights(self):
        volunteer = self.create_volunteer()
        older_event = self.create_event("older", end_offset=-10)
        newer_event = self.create_event("newer", end_offset=0)
        self.create_rated_participation(
            volunteer, older_event, rm_rating=0.4, kits_delivered=2, hours_logged=1
        )
        self.create_rated_participation(
            volunteer, newer_event, rm_rating=1.0, kits_delivered=2, hours_logged=1
        )

        update_volunteer_rating_rollup(volunteer.name)
        volunteer.reload()

        self.assertEqual(volunteer.rating_sample_size, 2)
        self.assertEqual(volunteer.effective_rating, 3.88)

    def test_logged_status_requires_rating(self):
        event = self.create_event()
        volunteer = self.create_volunteer()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "volunteer": volunteer.name,
                    "logging_status": "Logged",
                    "kits_delivered": 5,
                }
            ).insert(ignore_permissions=True)

    def test_non_rm_cannot_rate_on_insert(self):
        event = self.create_event()
        rm_user = frappe.get_doc(
            {
                "doctype": "User",
                "email": f"rm-{frappe.generate_hash(length=6)}@example.com",
                "first_name": "RM",
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)
        volunteer = self.create_volunteer(relationship_manager=rm_user.name)
        outsider = frappe.get_doc(
            {
                "doctype": "User",
                "email": f"outsider-{frappe.generate_hash(length=6)}@example.com",
                "first_name": "Outsider",
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)

        frappe.set_user(outsider.name)
        try:
            with self.assertRaises(frappe.ValidationError):
                frappe.get_doc(
                    {
                        "doctype": "Participation",
                        "event": event.name,
                        "volunteer": volunteer.name,
                        "logging_status": "Logged",
                        "kits_delivered": 5,
                        "hours_logged": 2.5,
                        "rm_rating": 0.8,
                    }
                ).insert(ignore_permissions=True)
        finally:
            frappe.set_user("Administrator")
