frappe.ui.form.on('Volunteer', {
    refresh: function(frm) {
        if (frappe.user_roles.includes("NGO Member") && 
            !frappe.user_roles.includes("NGO Admin") && 
            !frappe.user_roles.includes("NGO Coordinator")) {
            
            // Lock sensitive fields
            frm.set_df_property('membership_status', 'read_only', 1);
            frm.set_df_property('total_hours', 'read_only', 1);
        }
    }
});