frappe.ui.form.on("Attendance Request", {
	setup(frm) {
		lock_employee_for_non_hr(frm);
	},

	refresh(frm) {
		lock_employee_for_non_hr(frm);
		configure_wfh_submit_ux(frm);
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

function configure_wfh_submit_ux(frm) {
	if (frm.doc.docstatus !== 0) {
		volunteering.form_hints.clear(frm);
		return;
	}

	volunteering.form_hints.run_once(frm, "wfh_intro", async (token) => {
		const current = (
			await frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name")
		)?.message?.name;
		if (!volunteering.form_hints.is_current(frm, "wfh_intro", token)) {
			return;
		}

		const is_own = current && frm.doc.employee === current;
		const is_manager =
			current &&
			(
				await frappe.db.get_value("Employee", frm.doc.employee, "reports_to")
			)?.message?.reports_to === current;
		if (!volunteering.form_hints.is_current(frm, "wfh_intro", token)) {
			return;
		}

		if (is_own && !is_manager && !is_hr_user()) {
			frm.page.clear_primary_action();
			frm.disable_save = false;
			frm.page.set_primary_action(__("Save"), () => frm.save());
			volunteering.form_hints.set_intro(
				frm,
				__(
					"Save this request as a draft. Your reporting manager approves by <b>Submitting</b>. You cannot submit your own Attendance Request."
				),
				"blue"
			);
			$('.btn-primary:contains("Submit"), button:contains("Submit")').each(function () {
				const $b = $(this);
				const label = ($b.text() || "").trim();
				if (label === __("Submit") || label.includes("Submit")) {
					$b.hide();
				}
			});
		} else if (is_manager || is_hr_user()) {
			volunteering.form_hints.set_intro(
				frm,
				__("As manager/HR: review and <b>Submit</b> to approve this Attendance Request."),
				"orange"
			);
		} else {
			volunteering.form_hints.clear(frm);
		}
	});
}
