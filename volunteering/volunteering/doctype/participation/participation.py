import frappe
from frappe.model.document import Document

class Participation(Document):
    def before_insert(self):
        # Triggered when Web Form submits new record
        self.event = frappe.db.get_value("NGO Event", {"name": self.form_placeholder}, "name")
        if self.temp_phone:
            self.link_volunteer()

    def link_volunteer(self):
        # 1. Check if volunteer exists by phone
        v_name = frappe.db.get_value("Volunteer", {"mobile_number": self.temp_phone}, "name")
        print("Found existing volunteer")

        if not v_name:
            # 2. Create Volunteer record from redundant fields
            vol = frappe.get_doc({
                "doctype": "Volunteer",
                "first_name": self.temp_full_name,
                "email": self.temp_email,
                "mobile_number": self.temp_phone,
                "employee_id": self.temp_employee_id,
                "employer": self.temp_company
            })
            vol.insert(ignore_permissions=True)
            print("Created new volunteer")

            v_name = vol.name
        
        # 3. Map the link field
        self.volunteer = v_name