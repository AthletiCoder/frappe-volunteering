frappe.ui.form.on("Approval and Advance Limits", {
	refresh(frm) {
		frm.add_custom_button(__("Reset to Defaults"), () => {
			frappe.confirm(
				__("Replace all rows with the built-in default limits? Unsaved changes will be lost."),
				() => {
					frappe.call({
						method:
							"volunteering.volunteering.doctype.approval_and_advance_limits.approval_and_advance_limits.reset_to_defaults",
						freeze: true,
						freeze_message: __("Resetting…"),
						callback(r) {
							frappe.show_alert({
								message: __("Restored {0} default grade limits.", [r.message]),
								indicator: "green",
							});
							frm.reload_doc();
						},
					});
				}
			);
		});
	},
});
