from frappe import _


def get_dashboard_for_employee(data):
	data.setdefault("transactions", []).append(
		{
			"label": _("Daily Work Log"),
			"items": ["Daily Work Log"],
		}
	)
	return data
