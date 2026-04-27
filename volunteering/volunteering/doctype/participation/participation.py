import frappe
from frappe.model.document import Document
from frappe import _

class Participation(Document):
    def before_insert(self):
        self.ensure_event()

        if not self.volunteer and self.temp_phone:
            self.link_volunteer()

        if not self.volunteer:
            frappe.throw(
                _(
                    "Volunteer is required. Provide a volunteer or a valid phone number so we can auto-link the volunteer."
                )
            )

    def ensure_event(self):
        if self.event:
            return

        if self.form_placeholder and frappe.db.exists("NGO Event", self.form_placeholder):
            self.event = self.form_placeholder
            return

        frappe.throw(_("Event is required for participation registration."))

    def link_volunteer(self):
        logger = frappe.logger("volunteering")

        # 1. Check if volunteer exists by phone
        v_name = frappe.db.get_value("Volunteer", {"mobile_number": self.temp_phone}, "name")

        if not v_name:
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