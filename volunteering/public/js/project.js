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
		volunteering.project_budget.make_single_scroll_page(frm);
		volunteering.project_budget.toggle_account_budget_amounts(frm);
		if (
			!frm.is_new() &&
			(frappe.session.user === "Administrator" ||
				frappe.user_roles.includes("Accounts Manager"))
		) {
			frm.add_custom_button(__("Map expense labels"), () => {
				window.location.href =
					"/volunteering/project-account-mapping?project=" +
					encodeURIComponent(frm.doc.name);
			});
		}
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
								"Project budget: {0}. Expense category budgets: {1}. Spend is committed by Expense Claims and Purchase Orders, not advances.",
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
			? __("Required because expense category budget control is enabled.")
			: __(
					"Optional; the label still controls which expense categories employees may select.",
				),
	);
	frm.refresh_field("account_budgets");
};

volunteering.project_budget.make_single_scroll_page = function (frm) {
	const layout = frm.layout;
	if (!layout || !layout.tabs || !layout.tabs.length) {
		return;
	}

	volunteering.project_budget.add_single_page_styles();
	layout.wrapper.addClass("volunteering-project-single-page");

	layout.tabs.forEach((tab) => {
		if (tab.wrapper.children(".volunteering-project-tab-heading").length) {
			return;
		}

		const heading = $("<div>", {
			class: "volunteering-project-tab-heading",
			"data-fieldname": tab.df.fieldname,
		});
		$("<h4>", { class: "volunteering-project-tab-title" })
			.text(__(tab.df.label || "Details"))
			.appendTo(heading);
		heading.prependTo(tab.wrapper);
	});

	// The single-page view is intended for reviewing the whole Project form.
	// Open collapsed sections on refresh; users may still collapse them afterward.
	(layout.sections || []).forEach((section) => {
		if (section.df && section.df.collapsible && section.is_collapsed()) {
			section.collapse(false);
		}
	});
};

volunteering.project_budget.add_single_page_styles = function () {
	const style_id = "volunteering-project-single-page-styles";
	if (document.getElementById(style_id)) {
		return;
	}

	$("<style>", { id: style_id })
		.text(
			`
			.volunteering-project-single-page .form-tabs-list {
				display: none;
			}

			.volunteering-project-single-page .form-tab-content > .tab-pane:not(.hide) {
				display: block !important;
				opacity: 1 !important;
			}

			.volunteering-project-single-page .volunteering-project-tab-heading {
				border-bottom: 1px solid var(--border-color);
				padding: var(--padding-lg) var(--padding-md) var(--padding-sm);
			}

			.volunteering-project-single-page .volunteering-project-tab-title {
				font-size: var(--text-lg);
				font-weight: var(--weight-semibold);
				margin: 0;
			}
		`,
		)
		.appendTo(document.head);
};
