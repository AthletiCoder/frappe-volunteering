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
		}
	],
	"Purchase Order": [
		{
			"fieldname": "approval_level",
			"label": "Approval Level",
			"fieldtype": "Int",
			"insert_after": "project",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "escalation_reason",
			"label": "Escalation Reason",
			"fieldtype": "Small Text",
			"insert_after": "approval_level",
			"read_only": 0,
		}
	],
}
