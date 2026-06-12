frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Create Daily Work Log"), () => {
			frappe.new_doc("Daily Work Log", {
				employee: frm.doc.name,
			});
		});
	},
});
