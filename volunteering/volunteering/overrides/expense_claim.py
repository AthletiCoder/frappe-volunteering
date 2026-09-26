# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim

from volunteering.volunteering.expense_account_classification import (
	CLASSIFICATION_COMPLETE,
	validate_account_allocations,
)
from volunteering.volunteering.project_expense_accounts import (
	assign_and_validate_project_expense_accounts,
)


class VolunteeringExpenseClaim(ExpenseClaim):
	"""Expense Claim with Project-scoped account selection."""

	def set_expense_account(self, validate=False):
		# HRMS normally derives this from Expense Claim Type. In Sevamrita the
		# employee selects an approved Project expense label. Accounts supplies the
		# final ledger allocation before this claim is submitted and posted.
		if self.get("account_classification_status") == CLASSIFICATION_COMPLETE:
			grouped = validate_account_allocations(self)
			for row in self.expenses:
				if grouped.get(row.name):
					row.default_account = grouped[row.name][0].expense_account
			return
		assign_and_validate_project_expense_accounts(self)

	def get_gl_entries(self):
		"""Replace HRMS' one-expense-row debit with the final Accounts split."""
		grouped = validate_account_allocations(self)
		entries = super().get_gl_entries()
		start = 1 if self.grand_total else 0
		end = start + len(self.expenses)
		expense_entries = []
		accounts = []
		for expense in self.expenses:
			for allocation in grouped.get(expense.name, []):
				amount = allocation.allocated_amount
				accounts.append(allocation.expense_account)
				expense_entries.append(
					self.get_gl_dict(
						{
							"account": allocation.expense_account,
							"debit": self.set_base_fields_amount_value(amount),
							"debit_in_account_currency": amount,
							"debit_in_transaction_currency": amount,
							"against": self.employee,
							"cost_center": expense.cost_center or self.cost_center,
							"project": expense.project or self.project,
							"transaction_exchange_rate": self.exchange_rate,
						},
						account_currency=self.currency,
						item=expense,
					)
				)
		against = ",".join(dict.fromkeys(accounts))
		for entry in entries:
			if entry.get("against") == ",".join([row.default_account for row in self.expenses]):
				entry["against"] = against
		return entries[:start] + expense_entries + entries[end:]

	def set_base_fields_amount_value(self, amount):
		from frappe.utils import flt

		return flt(flt(amount) * flt(self.exchange_rate), self.precision("base_total_sanctioned_amount"))
