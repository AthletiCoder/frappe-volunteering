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
