from volunteering.volunteering.authority import LEGACY_BOARD_ROLES, LEGACY_ROLE_DEPT_HEAD

ACCOUNTING_APPROVAL_DOCTYPES = (
	"Expense Claim",
	"Purchase Order",
	"Purchase Invoice",
	"Employee Advance",
)

ACCOUNTS_ROLES = frozenset(
	{
		"Accounts Manager",
		"Accounts User",
		"Administrator",
		"System Manager",
	}
)

# Board access now comes from Employee Grade (see authority.user_is_board_level).
# These names only remain so dual-path checks keep working until the obsolete
# roles are deleted.
BOARD_ROLES = LEGACY_BOARD_ROLES

DEPT_HEAD_ROLE = LEGACY_ROLE_DEPT_HEAD
