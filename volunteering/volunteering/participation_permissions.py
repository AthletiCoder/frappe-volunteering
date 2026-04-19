import frappe

def get_permission_query_conditions(user):
    if not user: user = frappe.session.user
    
    roles = frappe.get_roles(user)
    if "NGO Admin" in roles or "NGO Coordinator" in roles:
        return ""

    if "NGO Member" in roles:
        # Filter: Only show records where the linked volunteer's user_id matches the session user
        return f"""
            `tabParticipation`.volunteer IN (
                SELECT name FROM `tabVolunteer` WHERE user_id = {frappe.db.escape(user)}
            )
        """
    return "1=0"