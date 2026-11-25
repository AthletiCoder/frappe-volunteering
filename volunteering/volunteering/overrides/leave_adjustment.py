import frappe
from hrms.hr.doctype.leave_adjustment.leave_adjustment import LeaveAdjustment


class SevamritaLeaveAdjustment(LeaveAdjustment):
	def validate(self):
		if not self.get("sf_policy_posting"):
			return super().validate()
		if not self.flags.hr_policy_posting:
			frappe.throw("Managed leave postings cannot be edited. Create a new reasoned adjustment.", frappe.PermissionError)
		posting = frappe.get_doc("HR Leave Posting", self.sf_policy_posting)
		if (posting.employee != self.employee or posting.leave_type != self.leave_type
			or abs(float(posting.days)) != float(self.leaves_to_adjust)
			or (posting.days > 0) != (self.adjustment_type == "Allocate")):
			frappe.throw("The leave adjustment does not match its source posting.")
		self.validate_non_zero_adjustment()
		# Policy-bound credits are already checked by the service; explicit HR
		# adjustments may grant or remove days beyond normal annual accrual.
		if posting.source not in {"HR adjustment", "Year adoption", "Carry forward", "Carry correction"}:
			self.validate_leave_balance()

	def before_cancel(self):
		if self.get("sf_policy_posting"):
			frappe.throw("Managed leave history is immutable. Create a reversing HR adjustment.")
