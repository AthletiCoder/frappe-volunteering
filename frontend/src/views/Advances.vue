<template>
	<div>
		<PageHeader
			eyebrow="Money"
			title="Advance Portal"
			subtitle="Status, leftover cash, and claims tagged to each advance."
		>
			<template #actions>
				<a class="btn-secondary text-sm" href="/app/employee-advance/new">New Advance</a>
				<button class="btn-primary text-sm" type="button" :disabled="loading" @click="load">
					{{ loading ? "Loading…" : "Refresh" }}
				</button>
			</template>
		</PageHeader>

		<div v-if="error" class="text-bad mb-4">{{ error }}</div>

		<div
			v-for="adv in advances"
			:key="adv.name"
			class="rounded-2xl border border-line bg-surface shadow-soft p-4 mb-4 hover:shadow-lift transition-shadow duration-200"
		>
			<div class="flex justify-between gap-3 flex-wrap">
				<div>
					<a class="font-semibold text-accent hover:underline" :href="adv.route">{{ adv.name }}</a>
					<div class="text-sm text-muted">
						{{ adv.purpose || "—" }} · {{ adv.status }} · {{ adv.workflow_state || "" }}
					</div>
				</div>
				<span class="px-2 py-0.5 rounded-full text-xs font-semibold h-fit" :class="residualClass(adv.residual_pct)">
					Residual {{ Math.round(adv.residual_pct || 0) }}%
				</span>
			</div>

			<div class="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
				<div v-for="s in stats(adv)" :key="s.label" class="rounded-xl bg-soft p-2">
					<div class="text-xs text-muted">{{ s.label }}</div>
					<div class="font-semibold text-ink">{{ s.value }}</div>
				</div>
			</div>

			<div class="mt-3 text-sm">
				<div class="font-medium mb-1 text-ink">Linked Expense Claims</div>
				<div v-if="!(adv.expense_claims || []).length" class="text-muted">No expense claims linked yet.</div>
				<div v-for="c in adv.expense_claims || []" :key="c.name" class="mb-1">
					<a class="text-accent hover:underline" :href="c.route">{{ c.name }}</a>
					<span class="text-muted"> · {{ formatMoney(c.allocated_amount) }} · {{ c.status }}</span>
				</div>
			</div>

			<div class="mt-3 flex flex-wrap gap-2">
				<a class="btn-primary text-sm" :href="`/app/expense-claim/new?employee=${encodeURIComponent(adv.employee)}`"
					>New Expense Claim</a
				>
				<a class="btn-secondary text-sm" :href="adv.route">Open Advance</a>
			</div>
		</div>

		<div v-if="!advances.length && !loading" class="text-center text-muted py-10">
			No advances yet. Request one, get it paid by Accounts, then link claims via Get Advances.
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";
import PageHeader from "../components/PageHeader.vue";

const advances = ref([]);
const loading = ref(false);
const error = ref("");

function residualClass(pct) {
	if ((pct || 0) > 10) return "bg-bad-soft text-bad";
	if ((pct || 0) > 0) return "bg-warn-soft text-warn";
	return "bg-ok-soft text-ok";
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
