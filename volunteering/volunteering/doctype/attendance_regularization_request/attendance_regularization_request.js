frappe.ui.form.on("Attendance Regularization Request", {
	setup(frm) {
		if (frm.is_new()) {
			set_default_employee(frm);
		}
	},

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

async function set_default_employee(frm) {
	if (frm.doc.employee) {
		return;
	}

	const employee = (
		await frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name")
	)?.message?.name;

	if (employee) {
		frm.set_value("employee", employee);
	}
}
