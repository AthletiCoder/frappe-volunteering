import frappe
from frappe.model.document import Document
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, now_datetime
from volunteering.volunteering.doctype.volunteer.volunteer import (
    find_volunteer_by_mobile,
    format_mobile_number,
    upgrade_volunteer_mobile_number,
)

DEFAULT_HOURS_PER_KIT = 0.5
RATING_MAX_STARS = 5
RECENT_EVENT_WEIGHTS = [0.5, 0.3, 0.2]
GRID_EDITABLE_FIELDS = frozenset(
    {
        "status",
        "kits_requested",
        "kits_delivered",
        "shipping_status",
        "logging_status",
        "hours_logged",
        "temp_full_name",
        "temp_phone",
        "temp_email",
        "temp_employee_id",
        "temp_company",
        "temp_address",
        "comments",
    }
)


def is_registered_for_event(mobile, event):
    if not event or not frappe.db.exists("NGO Event", event):
        return False

    formatted = format_mobile_number(mobile)
    if not formatted:
        return False

    volunteer = find_volunteer_by_mobile(formatted)
    if not volunteer:
        return False

    return bool(frappe.db.exists("Participation", {"event": event, "volunteer": volunteer}))


@frappe.whitelist(allow_guest=True)
@rate_limit(key="check_event_registration", limit=20, seconds=60)
def check_event_registration(mobile, event):
    return {"registered": is_registered_for_event(mobile, event)}


class Participation(Document):
    def before_insert(self):
        self.ensure_event()

        if self.temp_phone:
            self.temp_phone = format_mobile_number(self.temp_phone)

        if not self.volunteer and self.temp_phone:
            self.link_volunteer()

        if not self.volunteer:
            frappe.throw(
                _(
                    "Volunteer is required. Provide a volunteer or a valid phone number so we can auto-link the volunteer."
                )
            )

        if is_registered_for_event(self.temp_phone, self.event):
            frappe.throw(_("You have already registered for this event."))

    def ensure_event(self):
        if self.event:
            return

        if self.form_placeholder and frappe.db.exists("NGO Event", self.form_placeholder):
            self.event = self.form_placeholder
            return

        frappe.throw(_("Event is required for participation registration."))

    def link_volunteer(self):
        logger = frappe.logger("volunteering")

        formatted_phone = format_mobile_number(self.temp_phone)
        if not formatted_phone:
            return

        self.temp_phone = formatted_phone
        v_name = find_volunteer_by_mobile(formatted_phone)

        if v_name:
            upgrade_volunteer_mobile_number(v_name, formatted_phone)
        elif not v_name:
            # 2. Create Volunteer record from redundant fields
            vol = frappe.get_doc({
                "doctype": "Volunteer",
                "first_name": self.temp_full_name,
                "email": self.temp_email,
                "mobile_number": self.temp_phone,
                "employee_id": self.temp_employee_id,
                "employer": self.temp_company,
                "address": self.temp_address
            })
            vol.insert(ignore_permissions=True)
            logger.info("Created volunteer from participation registration: %s", vol.name)

            v_name = vol.name
        
        # 3. Map the link field
        self.volunteer = v_name

    def validate(self):
        self._validate_rating_permissions()
        self._validate_rating_inputs()
        self._compute_effective_rating()

    def after_insert(self):
        self._refresh_volunteer_rating_rollups()

    def on_update(self):
        self._refresh_volunteer_rating_rollups()

    def on_trash(self):
        self._refresh_volunteer_rating_rollups(exclude_participation=self.name)

    def _refresh_volunteer_rating_rollups(self, exclude_participation=None):
        volunteer_names = set()
        if self.volunteer:
            volunteer_names.add(self.volunteer)

        previous_doc = self.get_doc_before_save()
        if previous_doc and previous_doc.volunteer:
            volunteer_names.add(previous_doc.volunteer)

        for volunteer_name in volunteer_names:
            update_volunteer_rating_rollup(
                volunteer_name, exclude_participation=exclude_participation
            )

    def _validate_rating_permissions(self):
        rating_fields = ("rm_rating", "rm_comment")
        previous_doc = self.get_doc_before_save()

        if previous_doc:
            rating_changed = any(
                self.get(field) != previous_doc.get(field) for field in rating_fields
            )
            if not rating_changed:
                return
        elif not any(self.get(field) for field in rating_fields):
            return

        if _is_rating_editor_allowed(self.volunteer):
            return

        frappe.throw(_("Only the assigned Relationship Manager can submit ratings."))

    def _validate_rating_inputs(self):
        rating_stars = _get_rm_rating_stars(self.rm_rating)

        if self.logging_status == "Logged" and not rating_stars:
            frappe.throw(_("Rating is required once Logging Status is Logged."))

        if rating_stars and (self.kits_delivered or 0) <= 0:
            frappe.throw(_("Kits Delivered must be greater than zero before rating."))

        if rating_stars and not 1 <= rating_stars <= RATING_MAX_STARS:
            frappe.throw(
                _("Rating must be between 1 and {0}.").format(RATING_MAX_STARS)
            )

    def _compute_effective_rating(self):
        self.expected_hours = 0
        self.delta_hours = 0
        self.effective_rating = 0

        base_rating = _get_rm_rating_stars(self.rm_rating)
        if not base_rating:
            return

        kits_delivered = float(self.kits_delivered or 0)
        if kits_delivered <= 0:
            return

        factor = _get_hours_per_kit(self.event)
        expected_hours = kits_delivered * factor
        delta_hours = float(self.hours_logged or 0) - expected_hours
        delta_ratio = delta_hours / expected_hours if expected_hours else 0
        delta_adjustment = max(min(delta_ratio * 0.8, 1.0), -1.0)
        effective_rating = max(
            min(base_rating + delta_adjustment, float(RATING_MAX_STARS)), 1.0
        )

        self.expected_hours = expected_hours
        self.delta_hours = delta_hours
        self.effective_rating = effective_rating


def _get_rm_rating_stars(rating_value):
    """Convert Frappe Rating field value (0-1 fraction) to a 1-5 star scale."""
    value = flt(rating_value or 0)
    if value <= 0:
        return 0

    # Support legacy Float entries stored directly as 1-5.
    if value > 1:
        return max(min(value, RATING_MAX_STARS), 1)

    return value * RATING_MAX_STARS


def _is_rating_editor_allowed(volunteer_name):
    roles = set(frappe.get_roles(frappe.session.user))
    if {"System Manager", "NGO Admin"} & roles:
        return True

    relationship_manager = frappe.db.get_value(
        "Volunteer", volunteer_name, "relationship_manager"
    )
    return bool(relationship_manager and relationship_manager == frappe.session.user)


def _get_hours_per_kit(event_name):
    project = frappe.db.get_value("NGO Event", event_name, "project")
    if not project:
        return DEFAULT_HOURS_PER_KIT

    factor = frappe.db.get_value("Project", project, "hours_per_kit")
    try:
        factor = float(factor or 0)
    except (TypeError, ValueError):
        factor = 0

    return factor if factor > 0 else DEFAULT_HOURS_PER_KIT


def update_volunteer_rating_rollup(volunteer_name, exclude_participation=None):
    filters = [volunteer_name]
    exclude_clause = ""
    if exclude_participation:
        exclude_clause = "AND p.name != %s"
        filters.append(exclude_participation)

    rows = frappe.db.sql(
        f"""
        SELECT
            p.effective_rating
        FROM `tabParticipation` p
        LEFT JOIN `tabNGO Event` e ON e.name = p.event
        WHERE
            p.volunteer = %s
            AND IFNULL(p.effective_rating, 0) > 0
            {exclude_clause}
        ORDER BY COALESCE(e.enddate, e.startdate, p.modified) DESC
        LIMIT 3
        """,
        tuple(filters),
        as_dict=True,
    )

    rating_values = [float(row.effective_rating) for row in rows if row.effective_rating]
    if not rating_values:
        frappe.db.set_value(
            "Volunteer",
            volunteer_name,
            {
                "effective_rating": 0,
                "rating_sample_size": 0,
                "rating_last_updated": now_datetime(),
            },
            update_modified=False,
        )
        return

    active_weights = RECENT_EVENT_WEIGHTS[: len(rating_values)]
    total_weight = sum(active_weights)
    weighted_sum = sum(value * weight for value, weight in zip(rating_values, active_weights))
    volunteer_rating = weighted_sum / total_weight if total_weight else rating_values[0]

    frappe.db.set_value(
        "Volunteer",
        volunteer_name,
        {
            "effective_rating": round(volunteer_rating, 2),
            "rating_sample_size": len(rating_values),
            "rating_last_updated": now_datetime(),
        },
        update_modified=False,
    )


@frappe.whitelist()
def update_participation_field(name, fieldname, value=None, modified=None):
    """Update a single Participation field from Report View with full validation."""
    if fieldname in frappe.model.default_fields:
        frappe.throw(_("Cannot edit standard fields"))

    if fieldname not in GRID_EDITABLE_FIELDS:
        frappe.throw(_("Field {0} cannot be edited from the grid").format(fieldname))

    meta = frappe.get_meta("Participation")
    if not meta.has_field(fieldname):
        frappe.throw(_("Invalid field: {0}").format(fieldname))

    field = meta.get_field(fieldname)
    if field.read_only or field.fieldtype in ("Attach", "Attach Image", "Table"):
        frappe.throw(_("Field {0} cannot be edited from the grid").format(field.label))

    doc = frappe.get_doc("Participation", name)
    doc.check_permission("write")

    if modified:
        doc._original_modified = modified

    if fieldname == "temp_phone" and value:
        value = format_mobile_number(value)

    doc.set(fieldname, value)
    doc.save()

    return doc.as_dict()
