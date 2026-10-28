import assert from 'node:assert/strict';
import test from 'node:test';
import { purchaseTaxSummary } from '../src/lib/purchaseTaxBreakup.js';

const item = (amount, tax_breakup = {}, receipt_item = 'PRI-1') => ({ amount, tax_breakup, receipt_item, label: 'Kitchen plates' });

test('included CGST and SGST are separated for reference without changing gross cost', () => {
	const result = purchaseTaxSummary([item(1180, { cgst: '90', sgst: '90' })]);
	assert.equal(result.error, '');
	assert.equal(result.gross_total, 1180);
	assert.equal(result.base_total, 1000);
	assert.equal(result.tax_total, 180);
	assert.equal(result.items[0].cgst, 90);
});

test('optional empty amounts stay zero, and mixed per-item tax methods sum in paise', () => {
	const result = purchaseTaxSummary([item(.3, { other_tax: '.1' }), item(118, { igst: 18 }, 'PRI-2'), item(500, {}, 'PRI-3')]);
	assert.equal(result.error, '');
	assert.equal(result.gross_total, 618.3);
	assert.equal(result.tax_total, 18.1);
	assert.equal(result.base_total, 600.2);
});

test('invalid, negative, over-precise and excessive tax amounts are rejected', () => {
	for (const cgst of [-1, NaN, Infinity, 'oops', '.001', 1181]) assert.ok(purchaseTaxSummary([item(1180, { cgst })]).error);
	assert.ok(purchaseTaxSummary([item(1180, { cgst: 700, sgst: 700 })]).error);
});

test('IGST and CGST/SGST cannot be mixed on the same bill item', () => {
	assert.match(purchaseTaxSummary([item(1180, { cgst: 90, igst: 90 })]).error, /either IGST/);
});
