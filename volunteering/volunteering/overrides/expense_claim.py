# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim

from volunteering.volunteering.project_expense_accounts import (
	assign_and_validate_project_expense_accounts,
)


class VolunteeringExpenseClaim(ExpenseClaim):
	"""Expense Claim with Project-scoped account selection."""

	def set_expense_account(self, validate=False):
		# HRMS normally derives this from Expense Claim Type. In Sevamrita the
		# employee selects from the Project's restricted account allow-list.
		assign_and_validate_project_expense_accounts(self)
