frappe.provide("volunteering.accounting_workflow");

const WORKFLOW_ACTIONS = ["Approve", "Reject"];
const IDLE_WORKFLOW_STATES = ["Draft", "Rejected", "Approved"];

volunteering.accounting_workflow.refresh_form_tabs = function (frm) {
	// Shared helper only repairs blank panes; preserves the active tab.
	if (volunteering.form_hints && volunteering.form_hints.ensure_form_body_visible) {
		volunteering.form_hints.ensure_form_body_visible(frm);
	}
};

volunteering.accounting_workflow.setup_form = function (doctype) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			volunteering.accounting_workflow.render_actions(frm);
			volunteering.accounting_workflow.show_spend_hints(frm);
			volunteering.accounting_workflow.toggle_exception_fields(frm);
			if (doctype === "Employee Advance") {
				volunteering.accounting_workflow.lock_advance_employee(frm);
				volunteering.accounting_workflow.hide_advance_account_fields(frm);
				volunteering.accounting_workflow.setup_employee_advance_form(frm);
				volunteering.accounting_workflow.show_advance_disbursement_status(frm);
			}
			if (doctype === "Expense Claim") {
				volunteering.accounting_workflow.lock_claim_employee(frm);
				volunteering.accounting_workflow.show_advance_link_hints(frm);
				volunteering.accounting_workflow.hide_expense_claim_account_fields(frm);
				volunteering.accounting_workflow.setup_project_expense_account_selector(frm);
				volunteering.accounting_workflow.show_manager_float_hint(frm);
			}
			// Tab restore lives in form_shell_v9 (hash / active tab). Do not re-force tabs here.
		},
		is_emergency(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		total_claimed_amount(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		grand_total(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		project(frm) {
			volunteering.accounting_workflow.show_spend_hints(frm);
			if (doctype === "Expense Claim") {
				volunteering.accounting_workflow.on_expense_claim_project_change(frm);
			}
		},
		department(frm) {
			volunteering.accounting_workflow.show_spend_hints(frm);
		},
		reimbursement_source(frm) {
			volunteering.accounting_workflow.show_manager_float_hint(frm);
		},
		advance_amount(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
			if (doctype === "Employee Advance") {
				volunteering.accounting_workflow.update_advance_limit_hint(frm);
			}
		},
		employee(frm) {
			if (doctype === "Expense Claim") {
				volunteering.accounting_workflow.show_advance_link_hints(frm);
				volunteering.accounting_workflow.prefill_expense_claim_routing(frm);
				volunteering.accounting_workflow.show_manager_float_hint(frm);
			}
			if (doctype === "Employee Advance") {
				volunteering.accounting_workflow.on_advance_employee(frm);
			}
		},
	});
};

volunteering.accounting_workflow.is_board_level = function () {
	// Board authority lives on Employee Grade, so it can only be resolved server side.
	if (!volunteering.accounting_workflow._board_level_promise) {
		volunteering.accounting_workflow._board_level_promise = frappe
			.xcall("volunteering.volunteering.authority.user_is_board_level_for_session")
			.catch(() => false);
	}
	return volunteering.accounting_workflow._board_level_promise;
};

volunteering.accounting_workflow.lock_advance_employee = function (frm) {
	volunteering.accounting_workflow._lock_employee_to_self(frm);
};

volunteering.accounting_workflow.lock_claim_employee = function (frm) {
	volunteering.accounting_workflow._lock_employee_to_self(frm);
	frm.set_query("employee", function () {
		const staff_access = frappe.user.has_role([
			"Accounts Manager",
			"Accounts User",
			"HR Manager",
			"HR User",
			"System Manager",
		]);
		if (staff_access) {
			return { filters: { status: "Active" } };
		}
		return {
			query: "volunteering.volunteering.expense_claim_permissions.expense_claim_employee_query",
		};
	});
};

volunteering.accounting_workflow._lock_employee_to_self = function (frm) {
	const staff_access = frappe.user.has_role([
		"Accounts Manager",
		"Accounts User",
		"HR Manager",
		"HR User",
		"System Manager",
	]);
	if (staff_access) {
		return;
	}

	// Lock first, then unlock for board-level users once the check returns.
	frm.set_df_property("employee", "read_only", 1);
	if (frm.is_new() && !frm.doc.employee) {
		frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name").then((r) => {
			if (r && r.message && r.message.name) {
				frm.set_value("employee", r.message.name);
			}
		});
	}

	volunteering.accounting_workflow.is_board_level().then((is_board) => {
		if (is_board) {
			frm.set_df_property("employee", "read_only", 0);
		}
	});
};

volunteering.accounting_workflow.hide_advance_account_fields = function (frm) {
	const accounts = frappe.user.has_role(["Accounts Manager", "Accounts User", "System Manager"]);
	if (frm.fields_dict.advance_account) {
		frm.set_df_property("advance_account", "hidden", accounts ? 0 : 1);
	}
	// Advances are not tagged to a project; budget is on the settling Expense Claim.
	if (frm.fields_dict.project) {
		frm.set_df_property("project", "hidden", 1);
	}
};

volunteering.accounting_workflow.hide_expense_claim_account_fields = function (frm) {
	const accounts = frappe.user.has_role(["Accounts Manager", "Accounts User", "System Manager"]);
	if (frm.fields_dict.payable_account) {
		frm.set_df_property("payable_account", "hidden", accounts ? 0 : 1);
	}
};

volunteering.accounting_workflow.can_edit_project_expense_accounts = function (frm) {
	const accounts = frappe.user.has_role(["Accounts Manager", "Accounts User", "System Manager"]);
	return (
		frm.doc.docstatus === 0 &&
		(accounts ||
			["Draft", "Receipt Correction Required", "Rejected"].includes(frm.doc.workflow_state))
	);
};

volunteering.accounting_workflow.apply_project_expense_account_options = function (frm, options) {
	const grid = frm.fields_dict.expenses && frm.fields_dict.expenses.grid;
	if (!grid) {
		return;
	}
	grid.update_docfield_property("project_expense_account", "options", options || []);
	grid.update_docfield_property(
		"project_expense_account",
		"read_only",
		volunteering.accounting_workflow.can_edit_project_expense_accounts(frm) ? 0 : 1,
	);
	grid.grid_rows.forEach((grid_row) => {
		const control = grid_row.columns.project_expense_account?.field;
		if (control && control.set_data) {
			control.set_data(options || []);
		}
	});
	frm.refresh_field("expenses");
};

volunteering.accounting_workflow.setup_project_expense_account_selector = function (frm) {
	if (frm.doctype !== "Expense Claim") {
		return;
	}
	frm._project_expense_account_project = frm.doc.project || null;
	const project = frm.doc.project;
	const company = frm.doc.company;
	if (!project) {
		volunteering.accounting_workflow.apply_project_expense_account_options(frm, []);
		return;
	}
	const token = `${project}:${company || ""}`;
	frm._project_expense_account_token = token;
	frappe
		.xcall(
			"volunteering.volunteering.project_expense_accounts.get_project_expense_account_options",
			{
				project,
				company,
			},
		)
		.then((options) => {
			if (
				frm._project_expense_account_token !== token ||
				frm.doc.project !== project ||
				frm.doc.company !== company
			) {
				return;
			}
			volunteering.accounting_workflow.apply_project_expense_account_options(
				frm,
				options || [],
			);
			if (frm.doc.docstatus === 0) {
				frm.set_df_property(
					"expenses",
					"description",
					(options || []).length
						? __("Choose an approved expense category for the selected Project.")
						: __(
								"This Project has no mapped expense categories. Ask a Projects Manager to approve labels and an Accounts Manager to map them.",
							),
				);
			}
		});
};

volunteering.accounting_workflow.on_expense_claim_project_change = function (frm) {
	const previous = frm._project_expense_account_project;
	const current = frm.doc.project || null;
	if (previous && previous !== current) {
		(frm.doc.expenses || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "project_expense_account", "");
			frappe.model.set_value(row.doctype, row.name, "default_account", "");
		});
	}
	frm._project_expense_account_project = current;
	volunteering.accounting_workflow.setup_project_expense_account_selector(frm);
};

volunteering.accounting_workflow.setup_employee_advance_form = function (frm) {
	frm.set_query("employee", function () {
		const staff_access = frappe.user.has_role([
			"Accounts Manager",
			"Accounts User",
			"HR Manager",
			"HR User",
			"System Manager",
		]);
		const query = {
			filters: { status: "Active" },
		};
		if (staff_access) {
			query.query =
				"volunteering.volunteering.employee_advance_permissions.employee_advance_employee_query";
		}
		return query;
	});
	frm.set_query("advance_account", function () {
		if (!frm.doc.employee || !frm.doc.company) {
			return { filters: { name: ["in", []] } };
		}
		return {
			filters: {
				root_type: "Asset",
				is_group: 0,
				company: frm.doc.company,
				account_type: "Receivable",
			},
		};
	});
	if (frm.fields_dict.currency_section) {
		frm.set_df_property("currency_section", "collapsed", 1);
	}
	volunteering.accounting_workflow.on_advance_employee(frm);
	volunteering.accounting_workflow.update_advance_limit_hint(frm);
};

volunteering.accounting_workflow.prefill_expense_claim_routing = function (frm) {
	if (!frm.doc.employee) {
		return;
	}
	if (!frm.doc.expense_approver) {
		frappe
			.xcall(
				"volunteering.volunteering.approval_routing.get_expense_approver_for_employee",
				{
					employee: frm.doc.employee,
				},
			)
			.then((approver) => {
				if (approver) {
					frm.set_value("expense_approver", approver);
				}
			});
	}
	if (!frm.doc.currency) {
		frappe.db.get_value("Employee", frm.doc.employee, "company", (r) => {
			const company = r && r.message && r.message.company;
			if (!company) {
				frm.set_value("currency", "INR");
				return;
			}
			frappe.db.get_value("Company", company, "default_currency", (c) => {
				frm.set_value("currency", (c && c.message) || "INR");
			});
		});
	}
};

volunteering.accounting_workflow.on_advance_employee = function (frm) {
	if (!frm.doc.employee) {
		return;
	}
	const staff_access = frappe.user.has_role([
		"Accounts Manager",
		"Accounts User",
		"HR Manager",
		"HR User",
		"System Manager",
	]);
	if (staff_access && !frm.doc.company) {
		frappe
			.xcall("volunteering.volunteering.employee_advance_permissions.get_employee_company", {
				employee: frm.doc.employee,
			})
			.then((company) => {
				if (company) {
					frm.set_value("company", company);
				}
			});
	}
	if (!frm.doc.currency) {
		frappe.db.get_value("Employee", frm.doc.employee, "company", (r) => {
			const company = r && r.message && r.message.company;
			if (!company) {
				frm.set_value("currency", "INR");
				return;
			}
			frappe.db.get_value("Company", company, "default_currency", (c) => {
				frm.set_value("currency", (c && c.message) || "INR");
			});
		});
	}
	volunteering.accounting_workflow.update_advance_limit_hint(frm);
};

volunteering.accounting_workflow.update_advance_limit_hint = function (frm) {
	if (!frm.doc.employee || !frm.fields_dict.advance_amount) {
		return;
	}
	const employee = frm.doc.employee;
	volunteering.form_hints.run_once(frm, "advance_limit", (token) =>
		frappe
			.xcall(
				"volunteering.volunteering.employee_advance_controls.get_grade_advance_limit_for_employee",
				{
					employee,
				},
			)
			.then((data) => {
				if (
					!volunteering.form_hints.is_current(frm, "advance_limit", token) ||
					frm.doc.employee !== employee
				) {
					return;
				}
				const label = (data && data.label) || "";
				frm.set_df_property("advance_amount", "description", label);
			})
			.catch(() => {}),
	);
};

volunteering.accounting_workflow.show_advance_disbursement_status = function (frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}
	const paid = flt(frm.doc.paid_amount) > 0;
	const approved =
		frm.doc.workflow_state === "Approved" ||
		frm.doc.status === "Paid" ||
		frm.doc.status === "Unpaid";
	if (paid) {
		frm.dashboard.add_indicator(__("Paid to employee"), "green");
	} else if (approved) {
		frm.dashboard.set_headline(
			__("Approved — waiting for Accounts to pay this advance (Payment Entry)."),
		);
	} else if (frm.doc.workflow_state === "Pending Approval") {
		frm.dashboard.add_indicator(__("Awaiting approval"), "orange");
	}
};

volunteering.accounting_workflow.clear_advance_link_hints = function (frm) {
	volunteering.form_hints.clear(frm);
	frm._advance_hint_comment = null;
};

volunteering.accounting_workflow.show_advance_link_hints = function (frm) {
	volunteering.accounting_workflow.clear_advance_link_hints(frm);
	if (!frm.doc.employee || frm.doc.docstatus !== 0) {
		return;
	}

	// refresh + employee both fire on new forms; keep only the latest response
	const employee = frm.doc.employee;
	volunteering.form_hints.run_once(frm, "advance_link", (token) =>
		frappe
			.xcall(
				"volunteering.volunteering.employee_advance_controls.get_linkable_advances_hint",
				{
					employee,
				},
			)
			.then((msg) => {
				if (
					!volunteering.form_hints.is_current(frm, "advance_link", token) ||
					frm.doc.employee !== employee
				) {
					return;
				}
				volunteering.form_hints.clear(frm);
				if (!msg) {
					return;
				}
				volunteering.form_hints.set_headline(frm, msg, "blue");
			})
			.catch(() => {}),
	);
};

volunteering.accounting_workflow.spend_guide_html = function () {
	return __(
		'Prefer vendor payments for larger spends. See <a href="/help/accounts/how-to-spend" target="_blank">How to spend</a>.',
	);
};

volunteering.accounting_workflow.show_spend_hints = function (frm) {
	const show_spend =
		frm.doc.docstatus === 0 &&
		frm.doc.workflow_state === "Draft" &&
		frm.doctype !== "Purchase Invoice";
	volunteering.form_hints.run_once(frm, "spend_budget", () => {
		const spend = show_spend ? volunteering.accounting_workflow.spend_guide_html() : "";
		if (frm.doctype === "Employee Advance" || !frm.doc.project) {
			if (spend) {
				volunteering.form_hints.set_headline(frm, spend);
			}
			return Promise.resolve();
		}
		return frappe
			.xcall("volunteering.volunteering.budget_service.get_budget_snapshot", {
				project: frm.doc.project,
			})
			.then((snap) => {
				if (!snap) {
					if (spend) volunteering.form_hints.set_headline(frm, spend);
					return;
				}
				let budget = "";
				if (snap.allocated) {
					budget = __("Project ({0}): committed {1} of {2} approved ({3} available).", [
						snap.project_control,
						format_currency(snap.consumed),
						format_currency(snap.allocated),
						format_currency(snap.remaining),
					]);
				} else {
					budget = __(
						"Project budget control: {0}. Expense category budget control: {1}.",
						[snap.project_control, snap.account_control],
					);
				}
				const html = [spend, budget].filter(Boolean).join("<br>");
				if (html) {
					volunteering.form_hints.set_headline(frm, html);
				}
			});
	});
};

volunteering.accounting_workflow.toggle_exception_fields = function (frm) {
	const pending = frm.doc.workflow_state === "Pending Approval";
	const is_approver = frm.doc.pending_approver === frappe.session.user;
	const has_reason = !!(frm.doc.budget_override_reason || "").trim();
	const show_budget = has_reason || (pending && is_approver);

	if (frm.fields_dict.budget_section) {
		frm.set_df_property("budget_section", "hidden", show_budget ? 0 : 1);
		frm.set_df_property("budget_section", "collapsed", show_budget ? 0 : 1);
	}
	if (frm.fields_dict.budget_override_reason) {
		frm.set_df_property("budget_override_reason", "hidden", show_budget ? 0 : 1);
		frm.toggle_reqd("budget_override_reason", false);
	}

	if (frm.doctype === "Expense Claim" && frm.fields_dict.vendor_override_reason) {
		const show_vendor =
			!!(frm.doc.vendor_override_reason || "").trim() || !!frm.doc.is_emergency;
		frm.set_df_property("vendor_override_reason", "hidden", show_vendor ? 0 : 1);
	}
};

volunteering.accounting_workflow.render_review_buttons = function (frm, flags, transitions) {
	const actions = (transitions || []).filter((transition) =>
		WORKFLOW_ACTIONS.includes(transition.action),
	);
	const by_name = {};
	actions.forEach((t) => {
		by_name[t.action] = t;
	});

	if (flags.can_approve && by_name.Approve) {
		frm.page.set_primary_action(__("Approve"), () =>
			volunteering.accounting_workflow.apply_action(frm, "Approve"),
		);
	} else if (flags.strict_budget_blocked) {
		frm.dashboard.set_headline_alert(
			__("Strict budget exceeded. Escalate to an authorised budget approver or Reject."),
			"orange",
		);
	} else if (flags.manager_float_blocked && flags.manager_float_message) {
		frm.dashboard.set_headline_alert(flags.manager_float_message, "orange");
	}

	if (by_name.Reject && flags.can_reject) {
		frm.add_custom_button(
			__("Reject"),
			() => volunteering.accounting_workflow.apply_action(frm, "Reject"),
			__("Review"),
		);
	}

	// Escalate uses approval_routing.escalate_document — not a workflow transition.
	if (flags.can_escalate) {
		frm.add_custom_button(
			__("Escalate"),
			() => volunteering.accounting_workflow.escalate(frm),
			__("Review"),
		);
	}
};

volunteering.accounting_workflow.render_actions = function (frm) {
	const needs_receipt_review =
		frm.doctype === "Expense Claim" &&
		(frm.doc.workflow_state === "Pending Receipt Review" ||
			(frm.doc.docstatus === 1 &&
				frm.doc.workflow_state === "Approved" &&
				frm.doc.receipt_review_status !== "Verified"));
	if (needs_receipt_review) {
		volunteering.accounting_workflow.render_receipt_review_actions(frm);
		return;
	}
	if (frm.doc.docstatus !== 0 || !frm.doc.workflow_state) {
		return;
	}
	if (IDLE_WORKFLOW_STATES.includes(frm.doc.workflow_state)) {
		return;
	}

	frappe
		.xcall("volunteering.volunteering.approval_routing.get_approver_action_flags", {
			doctype: frm.doctype,
			name: frm.doc.name,
		})
		.then((flags) => {
			if (!flags || !flags.is_pending_approver) {
				return;
			}

			frappe.workflow
				.get_transitions(frm.doc)
				.then((transitions) =>
					volunteering.accounting_workflow.render_review_buttons(
						frm,
						flags,
						transitions,
					),
				)
				.catch(() =>
					volunteering.accounting_workflow.render_review_buttons(frm, flags, []),
				);
		});
};

volunteering.accounting_workflow.render_receipt_review_actions = function (frm) {
	frappe
		.xcall("volunteering.volunteering.receipt_review.get_receipt_review_action_flags", {
			name: frm.doc.name,
		})
		.then((flags) => {
			if (!flags || !flags.can_review) {
				return;
			}
			frm.page.set_primary_action(__("Verify Receipts"), () => {
				const fields = (flags.checklist || []).map((item) => ({
					fieldname: item.fieldname,
					label: __(item.label),
					fieldtype: "Check",
					reqd: 1,
				}));
				fields.push({
					fieldname: "notes",
					label: __("Review Notes"),
					fieldtype: "Small Text",
				});
				frappe.prompt(
					fields,
					(values) => {
						const checklist = {};
						(flags.checklist || []).forEach((item) => {
							checklist[item.fieldname] = Boolean(values[item.fieldname]);
						});
						volunteering.accounting_workflow.submit_receipt_review(
							frm,
							"verify",
							values.notes || "",
							checklist,
						);
					},
					__("Receipt audit checklist"),
					__("Verify Receipts"),
				);
			});
			if (flags.can_request_correction)
				frm.add_custom_button(
					__("Request Correction"),
					() => {
						frappe.prompt(
							{
								fieldname: "notes",
								label: __("Correction Required"),
								fieldtype: "Small Text",
								reqd: 1,
							},
							(values) =>
								volunteering.accounting_workflow.submit_receipt_review(
									frm,
									"request_correction",
									values.notes,
									{},
								),
							__("Request receipt correction"),
							__("Send Back"),
						);
					},
					__("Receipt Review"),
				);
		});
};

volunteering.accounting_workflow.submit_receipt_review = function (
	frm,
	decision,
	notes,
	checklist,
) {
	frappe.dom.freeze();
	frappe
		.xcall("volunteering.volunteering.receipt_review.review_receipts", {
			name: frm.doc.name,
			decision,
			notes,
			checklist,
		})
		.then(() => frm.reload_doc())
		.finally(() => frappe.dom.unfreeze());
};

volunteering.accounting_workflow.escalate = function (frm) {
	frappe.prompt(
		{
			fieldname: "escalation_reason",
			label: __("Escalation Reason"),
			fieldtype: "Small Text",
			reqd: 1,
		},
		(values) => {
			frappe.dom.freeze();
			frappe
				.xcall("volunteering.volunteering.approval_routing.escalate_document", {
					doctype: frm.doctype,
					name: frm.doc.name,
					escalation_reason: values.escalation_reason,
				})
				.then(() => frm.reload_doc())
				.finally(() => frappe.dom.unfreeze());
		},
		__("Escalate for higher approval"),
	);
};

volunteering.accounting_workflow.apply_action = function (frm, action) {
	const apply = () => {
		frappe.dom.freeze();
		frappe
			.xcall("frappe.model.workflow.apply_workflow", { doc: frm.doc, action })
			.then((doc) => {
				frappe.model.sync(doc);
				frm.refresh();
			})
			.catch(() => {
				// Uncollapse budget reason if Approve failed for missing reason
				if (action === "Approve" && frm.fields_dict.budget_section) {
					frm.set_df_property("budget_section", "hidden", 0);
					frm.set_df_property("budget_section", "collapsed", 0);
					frm.set_df_property("budget_override_reason", "hidden", 0);
				}
			})
			.finally(() => frappe.dom.unfreeze());
	};

	if (frm.is_dirty()) {
		frm.save().then(apply);
		return;
	}

	apply();
};

volunteering.accounting_workflow.show_manager_float_hint = function (frm) {
	if (frm.doc.doctype !== "Expense Claim" || frm.doc.docstatus !== 0) {
		return;
	}
	if ((frm.doc.reimbursement_source || "Out of Pocket") !== "Manager Advance") {
		return;
	}
	if (!frm.doc.employee) {
		return;
	}
	frappe
		.xcall("volunteering.volunteering.manager_float_service.get_manager_float_context", {
			employee: frm.doc.employee,
		})
		.then((ctx) => {
			if (!ctx) {
				return;
			}
			if (ctx.manager_employee && frm.fields_dict.manager_float_holder) {
				frm.set_value("manager_float_holder", ctx.manager_employee);
			}
			if (
				ctx.suggested_advance &&
				!frm.doc.manager_float_advance &&
				frm.fields_dict.manager_float_advance
			) {
				frm.set_value("manager_float_advance", ctx.suggested_advance);
			}
			const msg = ctx.total_residual
				? __(
						"Manager {0} has {1} available across {2} paid advance(s). After approval, " +
							"this claim settles from their advance (not your bank account).",
						[
							ctx.manager_name || ctx.manager_employee,
							format_currency(ctx.total_residual, frm.doc.currency),
							(ctx.fundable_advances || []).length,
						],
					)
				: __(
						"Manager {0} has no paid advance with residual. Your manager must Escalate or get an advance paid before approving.",
						[ctx.manager_name || ctx.manager_employee || __("your manager")],
					);
			frm.set_df_property("reimbursement_section", "description", msg);
		});
};

volunteering.accounting_workflow.setup_form("Expense Claim");
volunteering.accounting_workflow.setup_form("Purchase Order");
volunteering.accounting_workflow.setup_form("Employee Advance");

frappe.ui.form.on("Expense Claim Detail", {
	project_expense_account(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		// The trusted hidden Link is always recomputed by the server on save.
		frappe.model.set_value(cdt, cdn, "default_account", "");
		if (frm.doc.project && row.project !== frm.doc.project) {
			frappe.model.set_value(cdt, cdn, "project", frm.doc.project);
		}
	},
	form_render(frm) {
		volunteering.accounting_workflow.setup_project_expense_account_selector(frm);
	},
});
