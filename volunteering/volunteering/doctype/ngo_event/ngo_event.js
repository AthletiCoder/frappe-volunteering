frappe.ui.form.on("NGO Event", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Manage Participations"), () => {
			frappe.route_options = { event: frm.doc.name };
			frappe.set_route("List", "Participation", "Report");
		});
	},
});
