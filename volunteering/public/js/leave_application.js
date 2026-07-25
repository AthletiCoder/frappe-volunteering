frappe.ui.form.on("Leave Application", {
	setup(frm) {
		lock_employee_for_non_hr(frm);
	},

	refresh(frm) {
		set_default_leave_type(frm);
		lock_employee_for_non_hr(frm);
		lock_status_for_self(frm);
		show_leave_flow_hint(frm);
		setup_approver_actions(frm);
	},

	leave_category(frm) {
		show_leave_flow_hint(frm);
	},
});

const HR_ROLES = ["HR Manager", "HR User", "System Manager"];

function is_hr_user() {
	return frappe.user_roles.some((role) => HR_ROLES.includes(role));
}

async function lock_employee_for_non_hr(frm) {
	if (is_hr_user()) {
		frm.set_df_property("employee", "read_only", 0);
		return;
	}

	frm.set_df_property("employee", "read_only", 1);
	if (frm.is_new() && !frm.doc.employee) {
		const employee = (
			await frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name")
		)?.message?.name;
		if (employee) {
			frm.set_value("employee", employee);
		}
	}
}

async function lock_status_for_self(frm) {
	if (frm.doc.docstatus !== 0 || is_hr_user()) {
		return;
	}

	const current = (
		await frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name")
	)?.message?.name;
	if (current && frm.doc.employee === current) {
		frm.set_df_property("status", "read_only", 1);
		if (frm.doc.status !== "Open") {
			frm.set_value("status", "Open");
		}
	}
}

function show_leave_flow_hint(frm) {
	if (frm.doc.docstatus !== 0) {
		frm.set_intro("");
		return;
	}
	if (frm.doc.leave_approver === frappe.session.user || is_hr_user()) {
		frm.set_intro(
			__(
				"Use <b>Approve & Submit</b> or <b>Reject & Submit</b> to decide in one step. You cannot approve your own leave."
			),
			"blue"
		);
		return;
	}
	frm.set_intro(
		__(
			"Save with status <b>Open</b>. Your Leave Approver sets Approved/Rejected and submits. You cannot approve your own leave."
		),
		"blue"
	);
}

function set_default_leave_type(frm) {
	if (frm.doc.leave_type || !frm.is_new()) {
		return;
	}

	frappe.call({
		method: "volunteering.volunteering.leave_policy.get_leave_form_defaults",
		callback(r) {
			const leave_type = r.message && r.message.default_leave_type;
			if (leave_type && !frm.doc.leave_type) {
				frm.set_value("leave_type", leave_type);
			}
		},
	});
}

async function setup_approver_actions(frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.status !== "Open") {
		return;
	}

	const is_approver = frm.doc.leave_approver === frappe.session.user || is_hr_user();
	if (!is_approver) {
		return;
	}

	// Block self-approval in the UI too
	const self_emp = (
		await frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name")
	)?.message?.name;
	if (self_emp && frm.doc.employee === self_emp && !is_hr_user()) {
		return;
	}

	frm.page.set_primary_action(__("Approve & Submit"), () =>
		decide_and_submit(frm, "Approved")
	);
	frm.add_custom_button(__("Reject & Submit"), () => decide_and_submit(frm, "Rejected"), __(
		"Actions"
	));
}

function decide_and_submit(frm, status) {
	const apply = () => {
		frm.set_value("status", status).then(() => {
			frappe.dom.freeze(__("Submitting…"));
			frm
				.save("Submit")
				.then(() => {
					frappe.show_alert({
						message: status === "Approved" ? __("Leave approved") : __("Leave rejected"),
						indicator: status === "Approved" ? "green" : "red",
					});
				})
				.finally(() => frappe.dom.unfreeze());
		});
	};

	if (frm.is_dirty()) {
		frm.save().then(apply);
		return;
	}
	apply();
}
