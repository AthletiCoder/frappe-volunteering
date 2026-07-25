<template>
	<div>
		<div class="flex items-center justify-between mb-6 gap-3 flex-wrap">
			<div>
				<h1 class="text-2xl font-bold text-gray-900">Advance Portal</h1>
				<p class="text-sm text-gray-500">
					Status, residual, and expense claims tagged to each advance. Reportees can spend against a manager’s
					paid advance after claim approval.
				</p>
			</div>
			<div class="flex gap-2">
				<a class="px-3 py-1.5 rounded-lg border text-sm" href="/app/employee-advance/new">New Advance</a>
				<button class="px-3 py-1.5 rounded-lg bg-gray-900 text-white text-sm" @click="load">Refresh</button>
			</div>
		</div>

		<div v-if="error" class="text-red-600 mb-4">{{ error }}</div>

		<div v-for="adv in advances" :key="adv.name" class="rounded-xl border bg-white shadow-sm p-4 mb-4">
			<div class="flex justify-between gap-3 flex-wrap">
				<div>
					<a class="font-semibold text-blue-700 hover:underline" :href="adv.route">{{ adv.name }}</a>
					<div class="text-sm text-gray-500">
						{{ adv.purpose || "—" }} · {{ adv.status }} · {{ adv.workflow_state || "" }}
					</div>
				</div>
				<span class="px-2 py-0.5 rounded-full text-xs font-semibold h-fit" :class="residualClass(adv.residual_pct)">
					Residual {{ Math.round(adv.residual_pct || 0) }}%
				</span>
			</div>

			<div class="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
				<div v-for="s in stats(adv)" :key="s.label" class="rounded-lg bg-gray-50 p-2">
					<div class="text-xs text-gray-500">{{ s.label }}</div>
					<div class="font-semibold">{{ s.value }}</div>
				</div>
			</div>

			<div class="mt-3 text-sm">
				<div class="font-medium mb-1">Linked Expense Claims</div>
				<div v-if="!(adv.expense_claims || []).length" class="text-gray-500">No expense claims linked yet.</div>
				<div v-for="c in adv.expense_claims || []" :key="c.name" class="mb-1">
					<a class="text-blue-700 hover:underline" :href="c.route">{{ c.name }}</a>
					<span class="text-gray-500"> · {{ formatMoney(c.allocated_amount) }} · {{ c.status }}</span>
				</div>
			</div>

			<div class="mt-3 flex gap-2">
				<a
					class="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm"
					:href="`/app/expense-claim/new?employee=${encodeURIComponent(adv.employee)}`"
					>New Expense Claim</a
				>
				<a class="px-3 py-1.5 rounded-lg border text-sm" :href="adv.route">Open Advance</a>
			</div>
		</div>

		<div v-if="!advances.length && !loading" class="text-center text-gray-500 py-10">
			No advances yet. Request one, get it paid by Accounts, then link claims via Get Advances.
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call } from "../lib/frappe";

const advances = ref([]);
const loading = ref(false);
const error = ref("");

function formatMoney(v) {
	return new Intl.NumberFormat(undefined, { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
		v || 0
	);
}

function residualClass(pct) {
	if ((pct || 0) > 10) return "bg-red-100 text-red-700";
	if ((pct || 0) > 0) return "bg-orange-100 text-orange-700";
	return "bg-green-100 text-green-700";
}

function stats(adv) {
	return [
		{ label: "Requested", value: formatMoney(adv.advance_amount) },
		{ label: "Paid", value: formatMoney(adv.paid_amount) },
		{ label: "Claimed", value: formatMoney(adv.claimed_amount) },
		{ label: "Returned", value: formatMoney(adv.return_amount) },
		{ label: "Residual", value: formatMoney(adv.residual) },
	];
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		const data = await call("volunteering.volunteering.advance_portal.get_my_advances");
		advances.value = (data && data.advances) || [];
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
