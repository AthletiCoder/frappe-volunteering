CUSTOM_FIELDS = {
	"Leave Application": [
		{
			"fieldname": "leave_category",
			"label": "Leave Category",
			"fieldtype": "Select",
			"options": "Planned\nEmergency\nSick",
			"insert_after": "leave_type",
			"reqd": 1,
			"default": "Planned",
			"in_list_view": 1,
		}
	],
}

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
		{
			"fieldname": "department",
			"label": "Department",
			"fieldtype": "Link",
			"options": "Department",
			"insert_after": "employee",
		},
		{
			"fieldname": "approval_level",
			"label": "Approval Level",
			"fieldtype": "Int",
			"insert_after": "expense_approver",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "escalation_reason",
			"label": "Escalation Reason",
			"fieldtype": "Small Text",
			"insert_after": "approval_level",
			"read_only": 0,
			"depends_on": "eval:doc.escalation_reason || ['Pending Department Head', 'Pending Accounts Review', 'Pending Board Member', 'Pending Board Chair'].includes(doc.workflow_state)",
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
		{
			"fieldname": "approval_level",
			"label": "Approval Level",
			"fieldtype": "Int",
			"insert_after": "department",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "escalation_reason",
			"label": "Escalation Reason",
			"fieldtype": "Small Text",
			"insert_after": "approval_level",
			"read_only": 0,
			"depends_on": "eval:doc.escalation_reason || ['Pending Department Head', 'Pending Accounts Review', 'Pending Board Member', 'Pending Board Chair'].includes(doc.workflow_state)",
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
	"Project": [
		{
			"fieldname": "department_budgets_section",
			"fieldtype": "Section Break",
			"label": "Department Budgets",
			"insert_after": "cost_center",
		},
		{
			"fieldname": "department_budgets",
			"label": "Department Budgets",
			"fieldtype": "Table",
			"options": "Project Department Budget",
			"insert_after": "department_budgets_section",
		},
	],
}
