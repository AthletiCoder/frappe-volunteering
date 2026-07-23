CUSTOM_FIELDS = {
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

_BUDGET_REASON_DEPENDS = (
	"eval:doc.budget_override_reason || "
	"doc.workflow_state=='Pending Approval'"
)

_VENDOR_REASON_DEPENDS = "eval:doc.vendor_override_reason || doc.is_emergency"


def _approval_routing_fields(insert_after_anchor, emergency_label="Emergency Purchase"):
	"""Shared Approval tab + Exceptions + Budget sections for EC / PO / EA."""
	return [
		{
			"fieldname": "approval_routing_tab",
			"fieldtype": "Tab Break",
			"label": "Approval & Routing",
			"insert_after": insert_after_anchor,
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
		{
			"fieldname": "is_emergency",
			"label": emergency_label,
			"fieldtype": "Check",
			"insert_after": "exceptions_section",
			"default": "0",
		},
		{
			"fieldname": "budget_section",
			"fieldtype": "Section Break",
			"label": "Budget Exceedance",
			"insert_after": "is_emergency",
			"collapsible": 1,
			"collapsed": 1,
			"depends_on": _BUDGET_REASON_DEPENDS,
		},
		{
			"fieldname": "budget_override_reason",
			"label": "Budget Exceedance Reason",
			"fieldtype": "Small Text",
			"insert_after": "budget_section",
			"description": "Required when approving a spend that exceeds the department budget.",
			"depends_on": _BUDGET_REASON_DEPENDS,
		},
	]


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
		*_approval_routing_fields("expense_approver"),
		{
			"fieldname": "vendor_override_reason",
			"label": "Vendor Payment Override Reason",
			"fieldtype": "Small Text",
			"insert_after": "is_emergency",
			"depends_on": _VENDOR_REASON_DEPENDS,
			"description": (
				"Required when reimbursing above the vendor payment threshold "
				"without using a Purchase Order."
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
			"reqd": 1,
		},
		*_approval_routing_fields("project", emergency_label="Emergency"),
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
			"fieldname": "department_budgets_section",
			"fieldtype": "Section Break",
			"label": "Department Budgets",
			"insert_after": "cost_center",
			"collapsible": 1,
			"collapsed": 0,
		},
		{
			"fieldname": "department_budgets",
			"label": "Department Budgets",
			"fieldtype": "Table",
			"options": "Project Department Budget",
			"insert_after": "department_budgets_section",
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
