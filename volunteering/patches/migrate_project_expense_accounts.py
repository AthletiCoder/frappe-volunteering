from volunteering.volunteering.accounting_setup import backfill_project_expense_accounts


def execute():
	backfill_project_expense_accounts(seed_empty_projects=True)
