frappe.ui.form.on("Leave Application", {
	setup(frm) {
		lock_employee_for_non_hr(frm);
	},

	refresh(frm) {
		set_default_leave_type(frm);
		lock_employee_for_non_hr(frm);
		lock_status_for_self(frm);
		show_leave_flow_hint(frm);
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
	if (frm.doc.docstatus !== 0 || is_hr_user()) {
		frm.set_intro("");
		return;
	}
	// Keep only the approval-flow hint — advance-notice rules are enforced on save, not as banner text.
	frm.set_intro(
		__(
			"Save with status <b>Open</b>. Your Leave Approver sets Approved/Rejected and submits. You cannot approve your own leave."
		),
		"blue"
	);
	// #region agent log
	fetch("http://127.0.0.1:7494/ingest/940184ed-a7d0-4e09-a421-30599350bb5d", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-Debug-Session-Id": "4c4245",
		},
		body: JSON.stringify({
			sessionId: "4c4245",
			hypothesisId: "H2",
			location: "leave_application.js:show_leave_flow_hint",
			message: "intro set without advance-notice banner",
			data: {
				leave_category: frm.doc.leave_category,
				docstatus: frm.doc.docstatus,
			},
			timestamp: Date.now(),
			runId: "leave-ux",
		}),
	}).catch(() => {});
	// #endregion
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
