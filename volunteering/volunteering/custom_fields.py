CUSTOM_FIELDS = {
	"User": [
		{
			"fieldname": "work_log_reminder_opt_in",
			"label": "Morning Work Log Reminder",
			"fieldtype": "Check",
			"insert_after": "email",
			"default": "1",
			"description": "Email me when yesterday's Daily Work Log is still missing (paid staff).",
		}
	],
	"Leave Application": [
		{
			"fieldname": "leave_category",
			"label": "Leave Category",
			"fieldtype": "Select",
			"options": "Normal\nEmergency",
			"insert_after": "leave_type",
			"reqd": 1,
			"default": "Normal",
			"in_list_view": 1,
		}
	],
	"Attendance": [
		{
			"fieldname": "custom_regularized",
			"label": "Regularized",
			"fieldtype": "Check",
			"insert_after": "status",
			"read_only": 1,
			"description": "Set when attendance was adjusted via Attendance Regularization Request",
		}
	],
}

_SPEND_GUIDE_HTML = (
	'<p><a href="/help/accounts/how-to-spend" target="_blank">How to spend guide</a> · '
	'<a href="/help/accounts/tally-to-erpnext" target="_blank">Accounts: Tally → ERPNext</a> · '
	'<a href="/help/hr/home" target="_blank">HR guide</a></p>'
)

_PENDING_STATES_DEPENDS = (
	"eval:doc.escalation_reason || "
	"['Pending Approval', 'Pending Department Head', 'Pending Accounts Review', "
	"'Pending Board Member', 'Pending Board Chair'].includes(doc.workflow_state)"
)

_BUDGET_REASON_DEPENDS = "eval:doc.budget_override_reason || doc.workflow_state=='Pending Approval'"

_VENDOR_REASON_DEPENDS = "eval:doc.vendor_override_reason || doc.is_emergency"


def _approval_routing_fields(
	insert_after_anchor, emergency_label="Emergency Purchase", include_emergency=True
):
	"""Shared Approval tab + Exceptions + Budget sections for EC / PO / EA."""
	fields = [
		{
			"fieldname": "approval_routing_tab",
			"fieldtype": "Section Break",
			"label": "Approval & Routing",
			"insert_after": insert_after_anchor,
			"collapsible": 1,
		},
		{
			"fieldname": "approval_level",
			"label": "Approval Level",
			"fieldtype": "Int",
			"insert_after": "approval_routing_tab",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "pending_approver",
			"label": "Pending Approver",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "approval_level",
			"read_only": 1,
			"depends_on": _PENDING_STATES_DEPENDS,
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "escalation_reason",
			"label": "Escalation Reason",
			"fieldtype": "Small Text",
			"insert_after": "pending_approver",
			"depends_on": _PENDING_STATES_DEPENDS,
			"read_only": 1,
		},
		{
			"fieldname": "exceptions_section",
			"fieldtype": "Section Break",
			"label": "Exceptions",
			"insert_after": "escalation_reason",
			"collapsible": 1,
			"collapsed": 1,
		},
	]
	budget_after = "exceptions_section"
	if include_emergency:
		fields.append(
			{
				"fieldname": "is_emergency",
				"label": emergency_label,
				"fieldtype": "Check",
				"insert_after": "exceptions_section",
				"default": "0",
			}
		)
		budget_after = "is_emergency"
	fields.extend(
		[
			{
				"fieldname": "budget_section",
				"fieldtype": "Section Break",
				"label": "Budget Exceedance",
				"insert_after": budget_after,
				"collapsible": 1,
				"collapsed": 1,
				"depends_on": _BUDGET_REASON_DEPENDS,
			},
			{
				"fieldname": "budget_override_reason",
				"label": "Budget Exceedance Reason",
				"fieldtype": "Small Text",
				"insert_after": "budget_section",
				"description": (
					"Required when an authorised override approves spending above a strict "
					"Project or Expense Account budget."
				),
				"depends_on": _BUDGET_REASON_DEPENDS,
			},
		]
	)
	return fields


ACCOUNTING_CUSTOM_FIELDS = {
	"Department": [
		{
			"fieldname": "department_head",
			"label": "Department Head",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "department_name",
		}
	],
	"Expense Claim": [
		*_approval_routing_fields("expense_approver", emergency_label="Emergency Expense"),
		{
			"fieldname": "emergency_date",
			"label": "Emergency Date",
			"fieldtype": "Date",
			"insert_after": "is_emergency",
			"depends_on": "eval:doc.is_emergency",
		},
		{
			"fieldname": "emergency_reason",
			"label": "Emergency Reason",
			"fieldtype": "Small Text",
			"insert_after": "emergency_date",
			"depends_on": "eval:doc.is_emergency",
			"description": (
				"Explain the emergency and why the normal prior-purchase process could not be followed."
			),
		},
		{
			"fieldname": "vendor_override_reason",
			"label": "Vendor Payment Override Reason",
			"fieldtype": "Small Text",
			"insert_after": "emergency_reason",
			"depends_on": _VENDOR_REASON_DEPENDS,
			"description": (
				"Required when reimbursing above the vendor payment threshold without using a Purchase Order."
			),
		},
		{
			"fieldname": "reimbursement_section",
			"fieldtype": "Section Break",
			"label": "Reimbursement Source",
			"insert_after": "vendor_override_reason",
			"collapsible": 1,
		},
		{
			"fieldname": "reimbursement_source",
			"label": "Reimbursement Source",
			"fieldtype": "Select",
			"options": "Out of Pocket\nManager Advance",
			"insert_after": "reimbursement_section",
			"default": "Out of Pocket",
			"description": (
				"Manager Advance: settle from your reporting manager's paid advance "
				"after approval (no bank reimbursement to you). "
				"Not available when you already have your own unsettled paid advance."
			),
		},
		{
			"fieldname": "manager_float_holder",
			"label": "Manager",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "reimbursement_source",
			"read_only": 1,
			"depends_on": "eval:doc.reimbursement_source=='Manager Advance'",
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "manager_float_advance",
			"label": "Manager's Advance",
			"fieldtype": "Link",
			"options": "Employee Advance",
			"insert_after": "manager_float_holder",
			"read_only": 1,
			"depends_on": "eval:doc.reimbursement_source=='Manager Advance'",
			"ignore_user_permissions": 1,
			"description": (
				"Suggested from your manager's paid advances with residual. "
				"Final settlement may use a different advance if the claim amount requires it."
			),
		},
		{
			"fieldname": "spend_guide_section",
			"fieldtype": "Section Break",
			"label": "Spend Guide",
			"insert_after": "approval_status",
			"collapsible": 1,
			"collapsed": 1,
		},
		{
			"fieldname": "spend_guide_html",
			"label": "Spend Guide",
			"fieldtype": "HTML",
			"insert_after": "spend_guide_section",
			"options": _SPEND_GUIDE_HTML,
		},
		{
			"fieldname": "receipt_review_section",
			"fieldtype": "Section Break",
			"label": "Receipt Review",
			"insert_after": "spend_guide_html",
			"collapsible": 1,
			"collapsed": 0,
			"depends_on": "eval:doc.workflow_state && doc.workflow_state!='Draft'",
		},
		{
			"fieldname": "receipt_review_status",
			"label": "Receipt Review Status",
			"fieldtype": "Select",
			"options": "Not Submitted\nPending Review\nVerified\nCorrection Required",
			"insert_after": "receipt_review_section",
			"default": "Not Submitted",
			"read_only": 1,
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "receipt_reviewed_by",
			"label": "Reviewed By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "receipt_review_status",
			"read_only": 1,
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "receipt_reviewed_on",
			"label": "Reviewed On",
			"fieldtype": "Datetime",
			"insert_after": "receipt_reviewed_by",
			"read_only": 1,
		},
		{
			"fieldname": "receipt_review_notes",
			"label": "Receipt Review Notes",
			"fieldtype": "Small Text",
			"insert_after": "receipt_reviewed_on",
			"read_only": 1,
		},
		{
			"fieldname": "receipt_review_checklist",
			"label": "Audit Checklist Result",
			"fieldtype": "Small Text",
			"insert_after": "receipt_review_notes",
			"read_only": 1,
		},
		{
			"fieldname": "reviewed_attachments",
			"label": "Reviewed Attachments (Audit Snapshot)",
			"fieldtype": "Long Text",
			"insert_after": "receipt_review_checklist",
			"read_only": 1,
			"hidden": 1,
			"description": "Immutable names and hashes of the files covered by the review.",
		},
	],
	"Expense Claim Detail": [
		{
			"fieldname": "project_expense_account",
			"label": "Project Expense Account",
			"fieldtype": "Autocomplete",
			"insert_after": "column_break_2",
			"reqd": 1,
			"in_list_view": 1,
			"print_width": "180px",
			"width": "200px",
			"description": (
				"Choose an Expense Account permitted for the selected Project. "
				"This does not provide Chart of Accounts or balance access."
			),
		},
		{
			"fieldname": "supplier_name",
			"label": "Supplier / Payee",
			"fieldtype": "Data",
			"insert_after": "description",
			"in_list_view": 1,
		},
		{
			"fieldname": "supplier_invoice_number",
			"label": "Receipt / Invoice Number",
			"fieldtype": "Data",
			"insert_after": "supplier_name",
		},
		{
			"fieldname": "receipt_attachment",
			"label": "Receipt Evidence",
			"fieldtype": "Attach",
			"insert_after": "supplier_invoice_number",
			"read_only": 1,
			"description": "Private evidence uploaded for this expense item through the employee portal.",
		},
	],
	"Purchase Order": [
		{
			"fieldname": "department",
			"label": "Department",
			"fieldtype": "Link",
			"options": "Department",
			"insert_after": "project",
		},
		*_approval_routing_fields("department"),
		{
			"fieldname": "spend_guide_section",
			"fieldtype": "Section Break",
			"label": "Spend Guide",
			"insert_after": "transaction_date",
			"collapsible": 1,
			"collapsed": 1,
		},
		{
			"fieldname": "spend_guide_html",
			"label": "Spend Guide",
			"fieldtype": "HTML",
			"insert_after": "spend_guide_section",
			"options": _SPEND_GUIDE_HTML,
		},
	],
	"Purchase Invoice": [
		{
			"fieldname": "department",
			"label": "Department",
			"fieldtype": "Link",
			"options": "Department",
			"insert_after": "project",
		},
	],
	"Employee Advance": [
		{
			"fieldname": "project",
			"label": "Project",
			"fieldtype": "Link",
			"options": "Project",
			"insert_after": "department",
			"reqd": 0,
			"hidden": 1,
			"description": "Auto-set for budget tracking; hidden from employees.",
		},
		*_approval_routing_fields("return_amount", include_emergency=False),
		{
			"fieldname": "spend_guide_section",
			"fieldtype": "Section Break",
			"label": "Spend Guide",
			"insert_after": "purpose",
			"collapsible": 1,
			"collapsed": 1,
		},
		{
			"fieldname": "spend_guide_html",
			"label": "Spend Guide",
			"fieldtype": "HTML",
			"insert_after": "spend_guide_section",
			"options": _SPEND_GUIDE_HTML,
		},
	],
	"Project": [
		{
			"fieldname": "parent_campaign",
			"label": "Parent Campaign",
			"fieldtype": "Link",
			"options": "Project",
			"insert_after": "project_type",
			"depends_on": "eval:doc.project_type=='Event'",
		},
		{
			"fieldname": "budget_status",
			"label": "Budget Status",
			"fieldtype": "Select",
			"options": "Active\nExhausted\nClosed",
			"default": "Active",
			"insert_after": "parent_campaign",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "project_budget_controls_section",
			"fieldtype": "Section Break",
			"label": "Project Budget Controls",
			"insert_after": "cost_center",
			"collapsible": 1,
			"collapsed": 0,
		},
		{
			"fieldname": "project_budget_control",
			"label": "Overall Project Budget Control",
			"fieldtype": "Select",
			"options": "No Control\nWarn Only\nStrict",
			"default": "No Control",
			"reqd": 1,
			"insert_after": "project_budget_controls_section",
			"description": (
				"No Control tracks only; Warn Only allows overruns with a warning; "
				"Strict requires an authorised override."
			),
		},
		{
			"fieldname": "total_approved_budget",
			"label": "Total Approved Budget",
			"fieldtype": "Currency",
			"non_negative": 1,
			"insert_after": "project_budget_control",
			"description": "Independent ceiling for all committed spending on this Project.",
		},
		{
			"fieldname": "account_budget_control",
			"label": "Expense Account Budget Control",
			"fieldtype": "Select",
			"options": "No Control\nWarn Only\nStrict",
			"default": "No Control",
			"reqd": 1,
			"insert_after": "total_approved_budget",
			"description": "Controls each Expense Account allocation independently.",
		},
		{
			"fieldname": "account_budgets",
			"label": "Allowed Expense Accounts & Budgets",
			"fieldtype": "Table",
			"options": "Project Account Budget",
			"insert_after": "account_budget_control",
			"description": (
				"These are the only Expense Accounts employees can select for this Project. "
				"Approved Budget is optional when Expense Account Budget Control is No Control."
			),
		},
		{
			"fieldname": "department_budgets_section",
			"fieldtype": "Section Break",
			"label": "Department Budgets",
			"insert_after": "account_budgets",
			"collapsible": 1,
			"collapsed": 0,
			"hidden": 1,
		},
		{
			"fieldname": "department_budgets",
			"label": "Department Budgets",
			"fieldtype": "Table",
			"options": "Project Department Budget",
			"insert_after": "department_budgets_section",
			"hidden": 1,
		},
	],
	"Payment Entry": [
		{
			"fieldname": "is_cash_payment",
			"label": "Cash Payment",
			"fieldtype": "Check",
			"insert_after": "mode_of_payment",
			"read_only": 1,
			"default": "0",
		},
	],
}

# Budget section follows vendor override on Expense Claim
for _field in ACCOUNTING_CUSTOM_FIELDS["Expense Claim"]:
	if _field.get("fieldname") == "budget_section":
		_field["insert_after"] = "vendor_override_reason"
		break
