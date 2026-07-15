frappe.ui.form.on("Attendance Regularization Request", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.doc.status !== "Open") {
			return;
		}
		frm.add_custom_button(__("Approve"), () => {
			frm.call("approve_request").then(() => frm.reload_doc());
		}, __("Actions"));
		frm.add_custom_button(__("Reject"), () => {
			frm.call("reject_request").then(() => frm.reload_doc());
		}, __("Actions"));
	},
});
