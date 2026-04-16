import frappe
from frappe.model.document import Document
from frappe import _

class NGOEvent(Document):
    def on_update(self):
        before_save = self.get_doc_before_save()
        old_status = before_save.status if before_save else None
        
        if self.status == "Shipping" and old_status != "Shipping":
            self.generate_reciprocations()

    def generate_reciprocations(self):
        recent_events = self.get_recent_events()
        volunteers = frappe.get_all("Volunteer", fields=["name"])
        
        # Counters for the summary message
        counts = {
            "Standard": 0,
            "Deluxe": 0,
            "Reminder": 0,
            "status_updated": 0
        }

        for v in volunteers:
            # 1. Calculate Membership Tier
            count = self.get_participation_count(v.name, recent_events)
            is_registered = frappe.db.exists("Participation", {"event": self.name, "volunteer": v.name})
            
            tier = "Inactive"
            if count >= 3: tier = "Star"
            elif is_registered: tier = "Active"

            # 2. Update Volunteer Status
            # We check if it actually changed to avoid unnecessary DB writes
            current_v_status = frappe.db.get_value("Volunteer", v.name, "status")
            if current_v_status != tier:
                frappe.db.set_value("Volunteer", v.name, "status", tier)
                counts["status_updated"] += 1

            # 3. Determine Hamper Type
            hamper_tier = None
            if is_registered:
                hamper_tier = "Deluxe" if tier == "Star" else "Standard"
            elif tier == "Star":
                hamper_tier = "Reminder"

            # 4. Create Reciprocation Record
            if hamper_tier:
                created = self.create_reciprocation(v.name, hamper_tier, is_registered)
                if created:
                    counts[hamper_tier] += 1

        self.show_summary_toast(counts)

    def show_summary_toast(self, counts):
        # Construct the summary message
        msg = _("<b>Reciprocation Generation Summary:</b><br>")
        msg += _("• Volunteers Updated: {0}<br>").format(counts['status_updated'])
        msg += _("• Deluxe Hampers: {0}<br>").format(counts['Deluxe'])
        msg += _("• Standard Hampers: {0}<br>").format(counts['Standard'])
        msg += _("• Star Reminders: {0}").format(counts['Reminder'])

        # frappe.msgprint shows a popup; frappe.show_alert shows a toast (bottom right)
        # Choosing msgprint here as it's harder to miss for critical batch actions
        frappe.msgprint(msg, title=_("Success"), indicator="green")

    def get_recent_events(self):
        return frappe.get_all("NGO Event", 
            filters={"status": ["in", ["Shipping", "Followup", "Closed"]], "name": ["!=", self.name]},
            order_by="date desc", limit=5, pluck="name")

    def get_participation_count(self, volunteer, events):
        if not events: return 0
        return frappe.db.count("Participation", {"volunteer": volunteer, "event": ["in", events]})

    def create_reciprocation(self, volunteer, tier, participation_exists):
        hamper = frappe.db.get_value("Gift Hamper", {"event": self.name, "tier": tier}, "name")
        
        if hamper:
            # Check if reciprocation already exists to avoid duplicates on re-save
            if not frappe.db.exists("Reciprocation", {"volunteer": volunteer, "event": self.name}):
                rec = frappe.get_doc({
                    "doctype": "Reciprocation",
                    "volunteer": volunteer,
                    "event": self.name,
                    "gift_hamper": hamper,
                    "status": "Pending",
                    "participation": frappe.db.get_value("Participation", {"event": self.name, "volunteer": volunteer}, "name") if participation_exists else None
                })
                rec.insert(ignore_permissions=True)
                return True
        return False