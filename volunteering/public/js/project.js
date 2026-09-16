frappe.provide("volunteering.project_budget");

frappe.ui.form.on("Project", {
	setup(frm) {
		frm.set_query("expense_account", "account_budgets", () => ({
			filters: {
				company: frm.doc.company,
				root_type: "Expense",
				is_group: 0,
				disabled: 0,
			},
		}));
	},
	refresh(frm) {
		volunteering.project_budget.toggle_account_budget_amounts(frm);
		if (!frm.doc.name || frm.is_new()) {
			return;
		}
		volunteering.form_hints.run_once(frm, "project_budget", () =>
			frappe
				.xcall("volunteering.volunteering.budget_service.get_budget_snapshot", {
					project: frm.doc.name,
				})
				.then((snap) => {
					if (!snap) {
						return;
					}
					if (!snap.allocated) {
						volunteering.form_hints.set_headline(
							frm,
							__(
								"Project budget: {0}. Expense Account budgets: {1}. Spend is committed by Expense Claims and Purchase Orders, not advances.",
								[snap.project_control, snap.account_control],
							),
						);
						return;
					}
					const allocated = format_currency(snap.allocated);
					const spent = format_currency(snap.consumed);
					const available = format_currency(snap.remaining);
					volunteering.form_hints.set_headline(
						frm,
						__("Project budget ({0}): Approved {1} · Committed {2} · Available {3}", [
							snap.project_control,
							allocated,
							spent,
							available,
						]),
					);
				}),
		);
	},
	account_budget_control(frm) {
		volunteering.project_budget.toggle_account_budget_amounts(frm);
	},
});

volunteering.project_budget.toggle_account_budget_amounts = function (frm) {
	const grid = frm.fields_dict.account_budgets && frm.fields_dict.account_budgets.grid;
	if (!grid) {
		return;
	}
	const controlled = (frm.doc.account_budget_control || "No Control") !== "No Control";
	grid.update_docfield_property("approved_amount", "reqd", controlled ? 1 : 0);
	grid.update_docfield_property(
		"approved_amount",
		"description",
		controlled
			? __("Required because Expense Account budget control is enabled.")
			: __("Optional; this row still controls whether employees may select the account."),
	);
	frm.refresh_field("account_budgets");
};
