app_name = "volunteering"
app_title = "Volunteering"
app_publisher = "Vadiraj Tirtha Das"
app_description = "To track volunteers, their activities and donations"
app_email = "varun@sevamrita.org"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "volunteering",
# 		"logo": "/assets/volunteering/logo.png",
# 		"title": "Volunteering",
# 		"route": "/volunteering",
# 		"has_permission": "volunteering.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/volunteering/css/volunteering.css"
# app_include_js = "/assets/volunteering/js/volunteering.js"

# include js, css files in header of web template
# web_include_css = "/assets/volunteering/css/volunteering.css"
# web_include_js = "/assets/volunteering/js/volunteering.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "volunteering/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_list_js = {
    "Participation": [
        "volunteering/doctype/participation/participation_list.js",
    ],
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "volunteering/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "volunteering.utils.jinja_methods",
# 	"filters": "volunteering.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "volunteering.install.before_install"
# after_install = "volunteering.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "volunteering.uninstall.before_uninstall"
# after_uninstall = "volunteering.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "volunteering.utils.before_app_install"
# after_app_install = "volunteering.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "volunteering.utils.before_app_uninstall"
# after_app_uninstall = "volunteering.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "volunteering.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# Permission Query Conditions
# This restricts which records appear in List View/Search
permission_query_conditions = {
    "Volunteer": "volunteering.volunteering.volunteer_permissions.get_permission_query_conditions",
    "Participation": "volunteering.volunteering.participation_permissions.get_permission_query_conditions",
    "Reciprocation": "volunteering.volunteering.reciprocation_permissions.get_permission_query_conditions",
}

# Override "Has Permission" logic for specific row-level updates
has_permission = {
    "Volunteer": "volunteering.volunteering.volunteer_permissions.has_permission",
}

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Purchase Order": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
		],
	},
	"Purchase Invoice": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
		],
		"before_submit": "volunteering.volunteering.accounting_controls.validate_purchase_invoice_po_chain",
	},
	"Expense Claim": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
		],
	},
	"Payment Entry": {
		"before_submit": "volunteering.volunteering.accounting_controls.validate_payment_entry",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"volunteering.tasks.all"
# 	],
# 	"daily": [
# 		"volunteering.tasks.daily"
# 	],
# 	"hourly": [
# 		"volunteering.tasks.hourly"
# 	],
# 	"weekly": [
# 		"volunteering.tasks.weekly"
# 	],
# 	"monthly": [
# 		"volunteering.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "volunteering.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "volunteering.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "volunteering.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "volunteering.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["volunteering.utils.before_request"]
# after_request = ["volunteering.utils.after_request"]

# Job Events
# ----------
# before_job = ["volunteering.utils.before_job"]
# after_job = ["volunteering.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"volunteering.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["NGO Admin", "NGO Coordinator", "NGO Member"]]]},
    {"dt": "Web Form", "filters": [["module", "=", "Volunteering"]]},
    
    {"doctype": "Custom Field", "filters": [["dt", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry"]]]},
    {"doctype": "Property Setter", "filters": [["doc_type", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry"]]]},

    {"doctype": "Workflow", "filters": [["document_type", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry"]]]},

    "Workflow State",
    "Workflow Action"
]