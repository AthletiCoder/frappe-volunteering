import frappe
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as frappe_get

from volunteering.volunteering.dashboard_utils import normalize_dashboard_filters

KITS_DISTRIBUTION_CHART = "Kits Distribution"


@frappe.whitelist()
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
	refresh=None,
):
	document_type = _get_document_type(chart_name, chart)
	if document_type is not None:
		filters = normalize_dashboard_filters(filters, document_type)

	result = frappe_get(
		chart_name=chart_name,
		chart=chart,
		no_cache=no_cache,
		filters=filters,
		from_date=from_date,
		to_date=to_date,
		timespan=timespan,
		time_interval=time_interval,
		heatmap_year=heatmap_year,
		refresh=refresh,
	)

	if _is_kits_distribution_chart(chart_name, chart) and result:
		return sort_kits_distribution_by_kit_value(result)

	return result


def sort_kits_distribution_by_kit_value(chart_config):
	labels = chart_config.get("labels") or []
	datasets = chart_config.get("datasets") or []
	if not labels or not datasets:
		return chart_config

	values = datasets[0].get("values") or []
	sorted_pairs = sorted(
		zip(labels, values),
		key=lambda pair: float(pair[0]) if str(pair[0]).replace(".", "", 1).isdigit() else pair[0],
	)

	chart_config["labels"] = [label for label, _value in sorted_pairs]
	datasets[0]["values"] = [value for _label, value in sorted_pairs]
	return chart_config


def _is_kits_distribution_chart(chart_name, chart):
	if chart_name == KITS_DISTRIBUTION_CHART:
		return True

	if chart:
		parsed = frappe.parse_json(chart) if isinstance(chart, str) else chart
		return parsed.get("chart_name") == KITS_DISTRIBUTION_CHART or parsed.get("name") == KITS_DISTRIBUTION_CHART

	return False


def _get_document_type(chart_name, chart):
	if chart_name:
		return frappe.db.get_value("Dashboard Chart", chart_name, "document_type")

	if chart:
		parsed = frappe.parse_json(chart) if isinstance(chart, str) else chart
		return parsed.get("document_type")

	return None
