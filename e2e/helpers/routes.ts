/** Vue SPA base path (keep in sync with frontend/src/main.js). */
export const APP_BASE = '/volunteering';

export function appUrl(...segments: string[]): string {
	const parts = segments.filter(Boolean);
	if (!parts.length) {
		return APP_BASE;
	}
	return [APP_BASE, ...parts].join('/');
}

export const ROUTES = {
	budgetHealth: appUrl('budget-health'),
	advances: appUrl('advances'),
	advanceDetail: (name: string) => appUrl('advances', encodeURIComponent(name)),
	myWork: '/desk/my-work',
	myExpenses: '/desk/my-expenses',
	login: '/login',
} as const;

/** Desk workspaces may live under /desk or /app depending on Frappe version. */
export const DESK_WORKSPACE_RE = {
	myWork: /\/(app|desk)\/my-work/,
	myExpenses: /\/(app|desk)\/my-expenses/,
} as const;
