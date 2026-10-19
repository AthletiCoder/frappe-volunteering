// Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
// See license.txt

frappe.listview_settings["De Addiction Pledge"] = {
	onload(listview) {
		if (!frappe.model.can_read("De Addiction Pledge Settings")) {
			return;
		}
		listview.page.add_inner_button(__("Settings"), () => {
			frappe.set_route("Form", "De Addiction Pledge Settings");
		});
	},
};
