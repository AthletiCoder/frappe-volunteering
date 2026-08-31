import { type Page, expect } from '@playwright/test';
import { ROUTES } from '../helpers/routes';

export class AdvancesPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto(ROUTES.advances);
		await this.page.waitForLoadState('networkidle');
	}

	heading() {
		return this.page.getByRole('heading', { name: 'Advance Portal', level: 1 });
	}

	refreshButton() {
		return this.page.getByRole('button', { name: 'Refresh' });
	}

	newAdvanceLink() {
		return this.page.getByRole('link', { name: 'New Advance' });
	}

	async expectLoaded() {
		await expect(this.page).toHaveURL(/\/volunteering\/advances/);
		await expect(this.heading()).toBeVisible();
		await expect(this.page.locator('#app')).toBeVisible();
		await expect(this.refreshButton()).toBeVisible({ timeout: 30000 });
	}

	managerFloatPanelHeading() {
		return this.page.getByRole('heading', { name: "Request from manager's advance", level: 2 });
	}

	teamFloatRequestsHeading() {
		return this.page.getByRole('heading', { name: 'Team reimbursement requests', level: 2 });
	}

	outOfPocketClaimLink() {
		return this.page.getByRole('link', { name: 'New claim (out of pocket)' });
	}

	managerFloatClaimLink() {
		return this.page.getByRole('link', { name: "New claim (manager's advance)" });
	}

	teamFloatRequestRow(claimName: string) {
		return this.page
			.locator('section')
			.filter({ has: this.teamFloatRequestsHeading() })
			.locator('div.rounded-xl.border.p-3')
			.filter({ has: this.page.getByRole('link', { name: claimName, exact: true }) });
	}

	teamFloatRequestStatus(claimName: string) {
		return this.teamFloatRequestRow(claimName).getByText(/^(Can fund|Escalate)$/, { exact: true });
	}

	async waitForTeamRequestsLoaded(): Promise<void> {
		await expect(this.page.getByText('Loading team requests…')).toBeHidden({ timeout: 30000 }).catch(() => {});
	}
}
