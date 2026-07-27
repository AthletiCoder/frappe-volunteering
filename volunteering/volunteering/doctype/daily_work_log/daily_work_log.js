frappe.ui.form.on("Daily Work Log", {
	setup(frm) {
		if (frm.is_new()) {
			set_default_employee(frm);
			if (!frm.doc.date) {
				frm.set_value("date", frappe.datetime.get_today());
			}
		}
	},

	refresh(frm) {
		update_total_hours(frm);
		setup_review_button(frm);
		lock_employee_for_non_hr(frm);
		frm.set_df_property("is_wfh", "hidden", 1);
		show_wfh_status_near_date(frm);
	},

	date(frm) {
		show_wfh_status_near_date(frm);
	},

	employee(frm) {
		show_wfh_status_near_date(frm);
	},

	items_add(frm) {
		update_total_hours(frm);
	},

	items_remove(frm) {
		update_total_hours(frm);
	},
});

frappe.ui.form.on("Daily Work Log Item", {
	time_spent_hours(frm) {
		update_total_hours(frm);
	},
});

const HR_ROLES = ["HR Manager", "HR User", "System Manager"];

function is_hr_user() {
	return frappe.user_roles.some((role) => HR_ROLES.includes(role));
}

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

async function lock_employee_for_non_hr(frm) {
	if (is_hr_user()) {
		frm.set_df_property("employee", "read_only", 0);
		return;
	}
	frm.set_df_property("employee", "read_only", 1);
	if (frm.is_new() && !frm.doc.employee) {
		await set_default_employee(frm);
	}
}

async function show_wfh_status_near_date(frm) {
	frm.set_df_property("date", "description", "");
	if (!frm.doc.employee || !frm.doc.date) {
		return;
	}

	const is_wfh = await frappe.call({
		method: "volunteering.volunteering.attendance_service.has_approved_wfh_request_for_employee",
		args: { employee: frm.doc.employee, attendance_date: frm.doc.date },
	});

	const yes = !!(is_wfh && is_wfh.message);
	if (yes) {
		frm.set_value("is_wfh", 1);
		frm.set_df_property(
			"date",
			"description",
			__("As per records, this date is Work From Home (approved Attendance Request).")
		);
	} else {
		if (frm.doc.is_wfh) {
			frm.set_value("is_wfh", 0);
		}
		frm.set_df_property("date", "description", "");
	}
}

function update_total_hours(frm) {
	const total_hours = (frm.doc.items || []).reduce(
		(sum, item) => sum + flt(item.time_spent_hours),
		0
	);
	frm.set_value("total_hours", total_hours);
}

function setup_review_button(frm) {
	if (frm.doc.docstatus !== 1 || frm.doc.status === "Reviewed") {
		return;
	}

	frm.add_custom_button(__("Mark as Reviewed"), () => {
		const d = new frappe.ui.Dialog({
			title: __("Mark as Reviewed"),
			fields: [
				{
					fieldname: "manager_remarks",
					label: __("Manager Remarks"),
					fieldtype: "Small Text",
					default: frm.doc.manager_remarks || "",
				},
			],
			primary_action_label: __("Mark Reviewed"),
			primary_action(values) {
				frappe.call({
					method: "mark_as_reviewed",
					doc: frm.doc,
					args: { manager_remarks: values.manager_remarks || "" },
					callback() {
						d.hide();
						frm.reload_doc();
					},
				});
			},
		});
		d.show();
	});
}
