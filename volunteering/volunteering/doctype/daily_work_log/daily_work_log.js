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
		frappe.call({
			method: "mark_as_reviewed",
			doc: frm.doc,
			callback() {
				frm.reload_doc();
			},
		});
	});
}
