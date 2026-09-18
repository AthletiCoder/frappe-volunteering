<template>
	<div>
		<PageHeader
			eyebrow="Accounts"
			title="Budget Health"
			subtitle="Whole-project and employee-facing expense-category budget controls."
		>
			<template #actions>
				<button
					class="btn-primary text-sm"
					type="button"
					:disabled="loading"
					@click="load"
				>
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
			<select
				v-model="statusFilter"
				class="border border-line rounded-xl px-3 py-2 text-sm bg-surface"
			>
				<option value="">All statuses</option>
				<option value="Active">Active</option>
				<option value="Exhausted">Fully used</option>
				<option value="Closed">Closed</option>
			</select>
			<select
				v-model="riskFilter"
				class="border border-line rounded-xl px-3 py-2 text-sm bg-surface"
			>
				<option value="">All health</option>
				<option value="risk">At risk (≥80%)</option>
				<option value="over">At or over budget</option>
			</select>
		</div>

		<div class="space-y-3">
			<article
				v-for="row in visibleRows"
				:key="row.project"
				class="rounded-2xl border border-line bg-surface shadow-soft overflow-hidden"
			>
				<div
					class="p-4 grid gap-3 md:grid-cols-[minmax(180px,1.4fr)_1fr_1fr_1fr_1fr] md:items-center"
				>
					<div>
						<a class="font-semibold text-accent hover:underline" :href="row.route">{{
							row.project
						}}</a>
						<div class="text-xs text-muted mt-1">
							{{ row.project_type || "No project type" }}
						</div>
					</div>
					<div class="text-sm">
						<div class="text-xs text-muted">Controls</div>
						<div>Project: {{ row.project_control }}</div>
						<div>Categories: {{ row.account_control }}</div>
					</div>
					<div class="text-sm">
						<div class="text-xs text-muted">Approved</div>
						<div class="font-semibold">{{ formatMoney(row.allocated) }}</div>
					</div>
					<div class="text-sm">
						<div class="text-xs text-muted">Committed / Available</div>
						<a class="text-accent" :href="spendRoute(row)">{{
							formatMoney(row.consumed)
						}}</a>
						<span>
							/
							{{
								row.has_project_budget ? formatMoney(row.remaining) : "No ceiling"
							}}</span
						>
					</div>
					<div>
						<span
							class="px-2 py-0.5 rounded-full text-xs font-semibold"
							:class="pillClass(row)"
						>
							{{ projectHealthLabel(row) }}
						</span>
						<div class="mt-2 h-2 rounded-full bg-soft overflow-hidden">
							<div
								class="h-full rounded-full"
								:style="barStyle(row.utilisation_pct)"
							/>
						</div>
					</div>
				</div>

				<details
					v-if="row.accounts && row.accounts.length"
					class="border-t border-line px-4 py-3"
				>
					<summary class="cursor-pointer text-sm font-semibold">
						Ledger-account summary ({{ row.accounts.length }})
					</summary>
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-sm min-w-[620px]">
							<thead class="text-left text-muted">
								<tr>
									<th class="py-2 pr-3">Expense Account</th>
									<th class="py-2 px-3 text-right">Approved</th>
									<th class="py-2 px-3 text-right">Committed</th>
									<th class="py-2 px-3 text-right">Available</th>
									<th class="py-2 pl-3">Health</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="account in row.accounts"
									:key="account.expense_account"
									class="border-t border-line"
								>
									<td class="py-2 pr-3">{{ accountLabel(account) }}</td>
									<td class="py-2 px-3 text-right">
										{{
											account.is_budgeted
												? formatMoney(account.allocated)
												: "Not allocated"
										}}
									</td>
									<td class="py-2 px-3 text-right">
										{{ formatMoney(account.consumed) }}
									</td>
									<td class="py-2 px-3 text-right">
										{{
											account.is_budgeted
												? formatMoney(account.remaining)
												: "—"
										}}
									</td>
									<td class="py-2 pl-3">
										{{
											account.is_budgeted
												? Math.round(account.utilisation_pct || 0) + "%"
												: "Unbudgeted"
										}}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</details>
			</article>
			<p v-if="!visibleRows.length && !loading" class="text-center text-muted py-8">
				No Project budgets match these filters.
			</p>
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
		if (statusFilter.value && (row.budget_status || "Active") !== statusFilter.value)
			return false;
		const pct = row.utilisation_pct || 0;
		if (riskFilter.value === "risk" && !(pct >= 80 && pct < 100)) return false;
		if (riskFilter.value === "over" && pct < 100) return false;
		return true;
	});
});

const summaryCards = computed(() => {
	const alloc = rows.value.reduce((sum, row) => sum + (row.allocated || 0), 0);
	const used = rows.value.reduce((sum, row) => sum + (row.consumed || 0), 0);
	const warn = rows.value.filter(
		(row) => (row.utilisation_pct || 0) >= 80 && (row.utilisation_pct || 0) < 100,
	).length;
	const over = rows.value.filter((row) => (row.utilisation_pct || 0) >= 100).length;
	return [
		{ label: "Approved", value: formatMoney(alloc), tone: "text-ink" },
		{ label: "Committed", value: formatMoney(used), tone: "text-ink" },
		{ label: "At risk (≥80%)", value: String(warn), tone: "text-warn" },
		{ label: "At/over budget", value: String(over), tone: "text-bad" },
	];
});

function statusLabel(status) {
	if (status === "Exhausted") return "Fully used";
	return status || "Active";
}

function projectHealthLabel(row) {
	if (!row.has_project_budget) return `${statusLabel(row.budget_status)} · No ceiling`;
	return `${statusLabel(row.budget_status)} · ${Math.round(row.utilisation_pct || 0)}%`;
}

function pillClass(row) {
	const pct = row.utilisation_pct || 0;
	if (row.budget_status === "Exhausted" || row.budget_status === "Closed" || pct >= 100)
		return "bg-bad-soft text-bad";
	if (pct >= 80) return "bg-warn-soft text-warn";
	return "bg-ok-soft text-ok";
}

function barStyle(pct) {
	const color =
		(pct || 0) >= 100 ? "var(--bad)" : (pct || 0) >= 80 ? "var(--warn)" : "var(--ok)";
	return { width: Math.min(pct || 0, 100) + "%", background: color };
}

function accountLabel(account) {
	if (account.expense_account === "__unassigned__") return "Unassigned account";
	return account.expense_account;
}

function spendRoute(row) {
	return `/desk/expense-claim?project=${encodeURIComponent(row.project || "")}`;
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		rows.value =
			(await call("volunteering.volunteering.budget_service.get_budget_health")) || [];
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
