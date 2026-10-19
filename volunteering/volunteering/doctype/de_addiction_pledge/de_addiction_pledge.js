// Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
// See license.txt

frappe.ui.form.on("De Addiction Pledge", {
	refresh(frm) {
		frm.set_df_property("pledge_uuid", "read_only", 1);
		if (frappe.model.can_read("De Addiction Pledge Settings")) {
			frm.add_custom_button(__("Settings"), () => {
				frappe.set_route("Form", "De Addiction Pledge Settings");
			});
		}
	},
});
