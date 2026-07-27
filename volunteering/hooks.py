app_name = "volunteering"
app_title = "Volunteering"
app_publisher = "Vadiraj Tirtha Das"
app_description = "To track volunteers, their activities and donations"
app_email = "varun@sevamrita.org"
app_license = "mit"

# Apps
# ------------------

required_apps = ["hrms"]

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
app_include_js = ["/assets/volunteering/js/form_hints.js"]

# Website route for Frappe UI SPA (falls back to Desk pages if not built)
website_route_rules = [
	{"from_route": "/volunteering/<path:app_path>", "to_route": "volunteering"},
	{"from_route": "/volunteering", "to_route": "volunteering"},
]

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
doctype_js = {
    "Employee": "volunteering/doctype/daily_work_log/employee_daily_work_log.js",
    "Leave Application": "public/js/leave_application.js",
    "Attendance Request": "public/js/attendance_request.js",
    "Expense Claim": "public/js/accounting_workflow.js",
    "Purchase Order": "public/js/accounting_workflow.js",
    "Employee Advance": "public/js/accounting_workflow.js",
    "Purchase Invoice": "public/js/purchase_invoice.js",
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
    "Daily Work Log": "volunteering.volunteering.daily_work_log_permissions.get_permission_query_conditions",
    "Expense Claim": "volunteering.volunteering.expense_claim_permissions.get_permission_query_conditions",
    "Employee Advance": "volunteering.volunteering.employee_advance_permissions.get_permission_query_conditions",
    "Manager Note": "volunteering.volunteering.manager_note_permissions.get_permission_query_conditions",
    "Attendance Request": "volunteering.volunteering.attendance_request_permissions.get_permission_query_conditions",
    "Attendance": "volunteering.volunteering.attendance_permissions.get_permission_query_conditions",
}

# Override "Has Permission" logic for specific row-level updates
has_permission = {
    "Volunteer": "volunteering.volunteering.volunteer_permissions.has_permission",
    "Daily Work Log": "volunteering.volunteering.daily_work_log_permissions.has_permission",
    "Expense Claim": "volunteering.volunteering.expense_claim_permissions.has_permission",
    "Employee Advance": "volunteering.volunteering.employee_advance_permissions.has_permission",
    "Manager Note": "volunteering.volunteering.manager_note_permissions.has_permission",
    "Attendance Request": "volunteering.volunteering.attendance_request_permissions.has_permission",
    "Attendance": "volunteering.volunteering.attendance_permissions.has_permission",
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
	"Purchase Invoice": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
			"volunteering.volunteering.accounting_controls.assign_department_from_owner",
			"volunteering.volunteering.budget_service.validate_budget_on_save",
		],
		"before_submit": "volunteering.volunteering.accounting_controls.validate_purchase_invoice_po_chain",
	},
	"Expense Claim": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
			"volunteering.volunteering.accounting_controls.assign_department_from_employee",
			"volunteering.volunteering.approval_routing.before_accounting_document_save",
			"volunteering.volunteering.budget_service.validate_budget_on_save",
			"volunteering.volunteering.spend_controls.validate_spend_controls",
			"volunteering.volunteering.reimbursement_controls.validate_reimbursement_cap",
		],
		# Approve sets docstatus=1 and calls submit() (skips before_save) — re-check budget here.
		"before_submit": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.approval_routing.sync_expense_claim_approval_status_before_submit",
			"volunteering.volunteering.budget_service.validate_budget_on_save",
		],
		"on_update": "volunteering.volunteering.approval_routing.on_accounting_workflow_state_change",
	},
	"Purchase Order": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
			"volunteering.volunteering.accounting_controls.assign_department_from_owner",
			"volunteering.volunteering.approval_routing.before_accounting_document_save",
			"volunteering.volunteering.budget_service.validate_budget_on_save",
			"volunteering.volunteering.spend_controls.validate_spend_controls",
		],
		"before_submit": [
			"volunteering.volunteering.budget_service.validate_budget_on_save",
		],
		"on_update": "volunteering.volunteering.approval_routing.on_accounting_workflow_state_change",
	},
	"Employee Advance": {
		"before_save": [
			"volunteering.volunteering.accounting_controls.set_cost_center_from_project",
			"volunteering.volunteering.accounting_controls.validate_project_has_cost_center",
			"volunteering.volunteering.employee_advance_controls.before_employee_advance_save",
			"volunteering.volunteering.approval_routing.before_accounting_document_save",
			"volunteering.volunteering.budget_service.validate_budget_on_save",
		],
		"before_submit": [
			"volunteering.volunteering.budget_service.validate_budget_on_save",
		],
		"on_update": "volunteering.volunteering.approval_routing.on_accounting_workflow_state_change",
	},
	"Payment Entry": {
		"before_submit": [
			"volunteering.volunteering.accounting_controls.validate_payment_entry",
			"volunteering.volunteering.spend_controls.validate_spend_controls",
		],
		"on_submit": "volunteering.volunteering.disbursement_notifications.on_payment_entry_submit",
	},
	"Leave Application": {
		"validate": "volunteering.volunteering.leave_policy.validate_leave_application",
	},
	"Attendance Request": {
		"validate": "volunteering.volunteering.attendance_request_permissions.validate_attendance_request",
	},
	"Employee": {
		"after_insert": "volunteering.volunteering.leave_setup.assign_default_leave_policy",
		"validate": "volunteering.volunteering.leave_pending.sync_leave_approver_from_reports_to",
	},
	"Project": {
		"validate": "volunteering.volunteering.budget_service.validate_project_department_budgets",
	},
}

after_migrate = [
	"volunteering.volunteering.leave_setup.after_migrate",
	"volunteering.volunteering.workspace_setup.ensure_defaults",
	"volunteering.volunteering.workspace_setup.backfill_participation_relationship_managers",
	"volunteering.volunteering.hr_dashboard_setup.ensure_hr_dashboards",
	"volunteering.volunteering.quick_links_setup.ensure_quick_links",
	"volunteering.volunteering.desk_icons_setup.ensure_desk_icons",
	"volunteering.volunteering.accounting_setup.after_migrate",
]

boot_session = "volunteering.volunteering.workspace_setup.boot_session"

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"volunteering.volunteering.api.digest.send_daily_donation_digest",
	],
	"weekly": [
		"volunteering.volunteering.accounting_dashboard.setup.send_weekly_pending_approval_reminder",
	],
	"cron": {
		"0 12 * * *": [
			"volunteering.volunteering.api.attendance_digest.run_noon_attendance_jobs",
		],
		"*/15 * * * *": [
			"volunteering.volunteering.api.reconcile.reconcile_pending_donations",
		],
	},
}

# CORS for Vercel donate site (also set site_config allow_cors)
before_request = [
	"volunteering.volunteering.api.cors.handle_donation_cors_preflight",
]
after_request = [
	"volunteering.volunteering.api.cors.apply_donation_cors_headers",
]

# Testing
# -------

# before_tests = "volunteering.install.before_tests"

# Extend DocType Class
# ------------------------------
extend_doctype_class = {
	"Attendance": ["volunteering.volunteering.attendance_override.AttendanceHolidayMixin"],
}

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.doctype.dashboard_chart.dashboard_chart.get": "volunteering.volunteering.dashboard_chart.get",
	"frappe.desk.doctype.number_card.number_card.get_result": "volunteering.volunteering.number_card.get_result",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Employee": "volunteering.volunteering.dashboard_overrides.get_dashboard_for_employee",
}

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
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "NGO Admin",
                    "NGO Coordinator",
                    "NGO Member",
                    "Executive Board Member",
                    "Executive Board Chairperson",
                ],
            ]
        ],
    },
    {"dt": "Web Form", "filters": [["module", "=", "Volunteering"]]},
    {"doctype": "Custom Field", "filters": [["dt", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry"]]]},
    {"doctype": "Property Setter", "filters": [["doc_type", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry"]]]},
    {"doctype": "Workflow", "filters": [["document_type", "in", ["Purchase Order", "Purchase Invoice", "Expense Claim", "Payment Entry", "Employee Advance"]]]},
    "Workflow State",
    "Workflow Action",
    {"doctype": "Custom Field", "filters": [["dt", "=", "Project"], ["fieldname", "=", "hours_per_kit"]]},
]