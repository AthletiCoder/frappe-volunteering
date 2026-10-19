// Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
// See license.txt

frappe.ui.form.on("De Addiction Pledge Settings", {
	refresh(frm) {
		if (frappe.model.can_read("De Addiction Pledge")) {
			frm.add_custom_button(__("View Pledges"), () => {
				frappe.set_route("List", "De Addiction Pledge");
			});
		}

		if (frappe.user.has_role("System Manager") || frappe.session.user === "Administrator") {
			frm.add_custom_button(__("Show API Key"), () => show_api_key(frm));
		}
	},
});

function show_api_key(frm) {
	frappe.call({
		method:
			"volunteering.volunteering.doctype.de_addiction_pledge_settings.de_addiction_pledge_settings.get_api_key",
		freeze: true,
		callback(r) {
			const key = r.message;
			if (!key) {
				return;
			}
			frappe.msgprint({
				title: __("API Key"),
				indicator: "blue",
				message: `
					<p>${__("Use this value in the X-Pledge-Api-Key header:")}</p>
					<p><code style="user-select:all;word-break:break-all;">${frappe.utils.escape_html(key)}</code></p>
					<p class="text-muted">${__("Keep this secret. Anyone with this key can confirm pledges.")}</p>
				`,
			});
			if (navigator.clipboard && navigator.clipboard.writeText) {
				navigator.clipboard.writeText(key).then(() => {
					frappe.show_alert({ message: __("API key copied to clipboard"), indicator: "green" });
				});
			}
		},
	});
}
