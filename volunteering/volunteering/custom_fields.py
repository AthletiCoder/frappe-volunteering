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
