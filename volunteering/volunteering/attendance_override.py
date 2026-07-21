from erpnext.controllers.status_updater import validate_status

from hrms.hr.utils import validate_active_employee

ATTENDANCE_STATUSES = [
	"Present",
	"Absent",
	"On Leave",
	"Half Day",
	"Work From Home",
	"Holiday",
]


class AttendanceHolidayMixin:
	"""Allow Holiday as a valid Attendance status (factory accountability model)."""

	def validate(self):
		validate_status(self.status, ATTENDANCE_STATUSES)
		validate_active_employee(self.employee)
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.validate_overlapping_shift_attendance()
		self.validate_employee_status()
		if self.status != "Holiday":
			self.check_leave_record()
