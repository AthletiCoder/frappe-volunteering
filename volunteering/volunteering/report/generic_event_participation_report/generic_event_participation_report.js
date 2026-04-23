// Copyright (c) 2026, Vadiraj Tirtha Das and contributors
// For license information, please see license.txt

frappe.query_reports["Generic Event Participation Report"] = {
	"filters": [
		{
			"fieldname": "event",
			"label": __("Event"),
			"fieldtype": "Link",
			"options": "NGO Event",
			"reqd": 1
		}
	]
};
