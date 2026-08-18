<template>
	<div>
		<PageHeader eyebrow="Accounts" title="Budget Health" subtitle="Spent vs approved budget by project and department.">
			<template #actions>
				<button class="btn-primary text-sm" type="button" :disabled="loading" @click="load">
					{{ loading ? "Loading…" : "Refresh" }}
				</button>
			</template>
		</PageHeader>

		<div v-if="error" class="text-bad mb-4">{{ error }}</div>

		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
			<div
				v-for="card in summaryCards"
				:key="card.label"
				class="rounded-2xl border border-line bg-surface p-4 shadow-soft"
			>
				<div class="text-xs text-muted">{{ card.label }}</div>
				<div class="text-xl font-bold mt-1" :class="card.tone">{{ card.value }}</div>
			</div>
		</div>

		<div class="flex flex-col sm:flex-row flex-wrap gap-2 mb-4">
			<input
				v-model="projectFilter"
				class="border border-line rounded-xl px-3 py-2 text-sm bg-surface min-w-0 flex-1"
				placeholder="Filter project"
			/>
			<select v-model="statusFilter" class="border border-line rounded-xl px-3 py-2 text-sm bg-surface">
				<option value="">All statuses</option>
				<option value="Active">Active</option>
				<option value="Exhausted">Fully used</option>
				<option value="Closed">Closed</option>
			</select>
			<select v-model="riskFilter" class="border border-line rounded-xl px-3 py-2 text-sm bg-surface">
				<option value="">All health</option>
				<option value="risk">At risk (≥80%)</option>
				<option value="over">Overspent</option>
			</select>
		</div>

		<div class="md:hidden space-y-3">
			<article
				v-for="row in visibleRows"
				:key="row.project + row.department"
				class="rounded-2xl border border-line bg-surface p-4 shadow-soft"
			>
				<a class="font-semibold text-accent" :href="row.route">{{ row.project }}</a>
				<div class="text-sm text-muted mt-1">{{ row.department }} · {{ statusLabel(row.budget_status) }}</div>
				<div class="flex justify-between text-sm mt-2">
					<span class="text-muted">Spent</span>
					<a class="text-accent" :href="spendRoute(row)">{{ formatMoney(row.consumed) }}</a>
				</div>
				<div class="flex justify-between text-sm">
					<span class="text-muted">Available</span>
					<span>{{ formatMoney(row.remaining) }}</span>
				</div>
				<div class="mt-2 h-2 rounded-full bg-soft overflow-hidden">
					<div class="h-full rounded-full" :style="barStyle(row.utilisation_pct)" />
				</div>
			</article>
			<p v-if="!visibleRows.length && !loading" class="text-center text-muted py-8">No department budgets match.</p>
		</div>

		<div class="max-md:hidden rounded-2xl border border-line bg-surface shadow-soft overflow-x-auto">
			<table class="w-full text-sm min-w-[720px]">
				<thead class="bg-soft text-left text-muted">
					<tr>
						<th class="px-3 py-2">Project</th>
						<th class="px-3 py-2">Type</th>
						<th class="px-3 py-2">Status</th>
						<th class="px-3 py-2">Department</th>
						<th class="px-3 py-2 text-right">Approved</th>
						<th class="px-3 py-2 text-right">Spent</th>
						<th class="px-3 py-2 text-right">Available</th>
						<th class="px-3 py-2">Health</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in visibleRows" :key="row.project + row.department" class="border-t border-line hover:bg-accent-soft">
						<td class="px-3 py-2">
							<a class="text-accent hover:underline" :href="row.route">{{ row.project }}</a>
						</td>
						<td class="px-3 py-2">{{ row.project_type || "—" }}</td>
						<td class="px-3 py-2">
							<span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="pillClass(row)">
								{{ statusLabel(row.budget_status) }}
							</span>
						</td>
						<td class="px-3 py-2">
							<a
								v-if="row.department"
								class="text-accent hover:underline"
								:href="`/app/department/${encodeURIComponent(row.department)}`"
								>{{ row.department }}</a
							>
						</td>
						<td class="px-3 py-2 text-right">{{ formatMoney(row.allocated) }}</td>
						<td class="px-3 py-2 text-right">
							<a class="text-accent hover:underline" :href="spendRoute(row)">{{ formatMoney(row.consumed) }}</a>
						</td>
						<td class="px-3 py-2 text-right">{{ formatMoney(row.remaining) }}</td>
						<td class="px-3 py-2 min-w-[140px]">
							<span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="pillClass(row)">
								{{ Math.round(row.utilisation_pct || 0) }}%
							</span>
							<div class="mt-1 h-2 rounded-full bg-soft overflow-hidden">
								<div class="h-full rounded-full" :style="barStyle(row.utilisation_pct)" />
							</div>
						</td>
					</tr>
					<tr v-if="!visibleRows.length && !loading">
						<td colspan="8" class="px-3 py-8 text-center text-muted">No department budgets match these filters.</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";
import PageHeader from "../components/PageHeader.vue";

const rows = ref([]);
const loading = ref(false);
const error = ref("");
const projectFilter = ref("");
const statusFilter = ref("");
const riskFilter = ref("");

const visibleRows = computed(() => {
	const q = (projectFilter.value || "").toLowerCase();
	return rows.value.filter((row) => {
		if (q && !(row.project || "").toLowerCase().includes(q)) return false;
		if (statusFilter.value && (row.budget_status || "Active") !== statusFilter.value) return false;
		const pct = row.utilisation_pct || 0;
		if (riskFilter.value === "risk" && !(pct >= 80 && pct < 100)) return false;
		if (riskFilter.value === "over" && pct < 100) return false;
		return true;
	});
});

const summaryCards = computed(() => {
	const alloc = rows.value.reduce((s, r) => s + (r.allocated || 0), 0);
	const used = rows.value.reduce((s, r) => s + (r.consumed || 0), 0);
	const warn = rows.value.filter((r) => (r.utilisation_pct || 0) >= 80 && (r.utilisation_pct || 0) < 100).length;
	const over = rows.value.filter((r) => (r.utilisation_pct || 0) >= 100).length;
	return [
		{ label: "Approved", value: formatMoney(alloc), tone: "text-ink" },
		{ label: "Spent", value: formatMoney(used), tone: "text-ink" },
		{ label: "At risk (≥80%)", value: String(warn), tone: "text-warn" },
		{ label: "Overspent", value: String(over), tone: "text-bad" },
	];
});

function statusLabel(status) {
	if (status === "Exhausted") return "Fully used";
	return status || "Active";
}

function pillClass(row) {
	const pct = row.utilisation_pct || 0;
	if (row.budget_status === "Exhausted" || row.budget_status === "Closed" || pct >= 100) return "bg-bad-soft text-bad";
	if (pct >= 80) return "bg-warn-soft text-warn";
	return "bg-ok-soft text-ok";
}

function barStyle(pct) {
	const color = (pct || 0) >= 100 ? "var(--bad)" : (pct || 0) >= 80 ? "var(--warn)" : "var(--ok)";
	return { width: Math.min(pct || 0, 100) + "%", background: color };
}

function spendRoute(row) {
	return `/app/expense-claim?project=${encodeURIComponent(row.project || "")}`;
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		rows.value = (await call("volunteering.volunteering.budget_service.get_budget_health")) || [];
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
