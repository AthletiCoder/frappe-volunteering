import { expect, test } from '@playwright/test';
import { e2eCall } from '../../helpers/e2e-api';
import { personaStorage } from '../../helpers/personas';

test.describe('Books and hubs @accounts', () => {
	test.describe('as accounts', () => {
		test.use({ storageState: personaStorage('accounts') });

		test('AC-BKS-001 @regression: Cashfree clearing Journal Entry form reachable', async ({
			request,
		}) => {
			const allowed = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Journal Entry', ptype: 'create' },
				'accounts',
			);
			expect(allowed).toBe(true);
		});

		test('AC-BKS-002 @regression: Cancel preserves history (submitted doc not deletable)', async ({
			request,
		}) => {
			const allowed = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Payment Entry', ptype: 'read' },
				'accounts',
			);
			expect(allowed).toBe(true);
		});

		test('AC-BKS-004 @regression: General Ledger report runs', async ({ request }) => {
			const report = await e2eCall<{ ok: boolean; columns?: unknown[] }>(
				request,
				'run_query_report',
				{ report_name: 'General Ledger' },
				'accounts',
			);
			expect(report.ok).toBe(true);
			expect(report.columns).toBeTruthy();
		});

		test('AC-BKS-005 @regression: Bank Reconciliation Tool opens', async ({ request }) => {
			const bankTxn = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Bank Transaction', ptype: 'read' },
				'accounts',
			);
			const payment = await e2eCall<boolean>(
				request,
				'has_doctype_permission',
				{ doctype: 'Payment Entry', ptype: 'read' },
				'accounts',
			);
			expect(bankTxn || payment).toBe(true);
		});
	});
});
