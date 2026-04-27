frappe.ui.form.on('Volunteer', {
    refresh: function(frm) {
        if (frappe.user_roles.includes("NGO Member") && 
            !frappe.user_roles.includes("NGO Admin") && 
            !frappe.user_roles.includes("NGO Coordinator")) {
            // Keep status as read-only for members from the form layer.
            frm.set_df_property('status', 'read_only', 1);
        }
    }
});