<template>
	<section v-if="actions.length" :class="panel ? 'action-panel' : ''">
		<h2 :class="panel ? 'flex items-center gap-2 px-4 pb-1 pt-4 text-[13px] font-semibold text-ink-2 sm:px-5' : 'mb-2 flex items-center gap-2 text-sm font-semibold text-ink'">
			<Icon :name="icon" size="sm" class="text-muted" />
			{{ title }}
		</h2>
		<div :class="variant === 'tiles' ? 'grid gap-0.5 p-1.5 pt-0.5 sm:grid-cols-2 sm:p-2 sm:pt-1 xl:grid-cols-3' : variant === 'dashboard' ? 'p-1.5 pt-0.5 sm:p-2 sm:pt-1' : 'grid grid-cols-1 gap-3 sm:grid-cols-2'">
			<article
				v-for="action in actions"
				:key="action.id"
				:data-action-id="action.id"
				:class="panel ? 'action-row min-w-0' : 'rounded-2xl border border-line bg-surface p-3 shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift'"
			>
				<a :href="action.route" class="group flex items-start gap-3 rounded-xl p-2.5 transition-colors duration-150 hover:bg-soft">
					<span
						:data-icon-name="visualFor(action.id).icon"
						:data-icon-tone="visualFor(action.id).tone"
						:class="[
							'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 ease-out group-hover:scale-105',
							`action-icon--${visualFor(action.id).tone}`,
						]"
					>
						<Icon :name="visualFor(action.id).icon" />
					</span>
					<div class="min-w-0 flex-1 pt-0.5">
						<div class="flex items-center gap-1 text-sm font-semibold text-ink">{{ action.label }}<Icon name="arrow-right" size="sm" class="ml-auto shrink-0 -translate-x-1 text-navy-600 opacity-0 transition-all duration-200 ease-out group-hover:translate-x-0 group-hover:opacity-100" /></div>
						<div class="mt-0.5 text-[13px] leading-snug text-muted" :class="variant === 'tiles' ? 'line-clamp-1' : variant === 'dashboard' ? 'line-clamp-2' : ''">{{ action.hint }}</div>
					</div>
				</a>
				<a
					v-if="action.list_route"
					:href="action.list_route"
					class="mb-1.5 ml-[3.875rem] inline-flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-muted transition-colors duration-150 hover:border-navy-200 hover:text-navy-900"
				>
					<span>{{ action.list_label }}</span>
					<span class="font-semibold tabular-nums text-ink">{{
						action.pending || 0
					}}</span>
				</a>
			</article>
		</div>
	</section>
</template>

<script setup>
import { computed } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
	title: { type: String, required: true },
	icon: { type: String, default: "spark" },
	actions: { type: Array, default: () => [] },
	variant: { type: String, default: "default" },
});

const actionVisuals = {
	projects: { icon: "folder", tone: "blue" },
	approved_projects: { icon: "folder-check", tone: "green" },
	create_project: { icon: "document-plus", tone: "blue" },
	my_project_requests: { icon: "document-history", tone: "violet" },
	review_project_proposals: { icon: "clipboard-check", tone: "amber" },
	manage_employees: { icon: "user-plus", tone: "cyan" },
	manage_users: { icon: "user-shield", tone: "violet" },
	my_team: { icon: "people", tone: "cyan" },
	log_work: { icon: "clock", tone: "blue" },
	wfh: { icon: "home", tone: "green" },
	leave: { icon: "calendar-away", tone: "violet" },
	fix_attendance: { icon: "calendar-check", tone: "amber" },
	advance: { icon: "coins", tone: "blue" },
	claim: { icon: "receipt", tone: "amber" },
	invoice_generator: { icon: "invoice", tone: "cyan" },
	invoice_expense_claim: { icon: "invoice-claim", tone: "green" },
	bank_account: { icon: "bank", tone: "green" },
	donations: { icon: "coins", tone: "green" },
	office_addresses: { icon: "map-pin", tone: "cyan" },
	how_to_spend: { icon: "guide", tone: "slate" },
	advance_disbursement: { icon: "money-out", tone: "blue" },
	advance_returns: { icon: "money-return", tone: "amber" },
	classify_claims: { icon: "receipt", tone: "violet" },
	settle_claims: { icon: "money-out", tone: "green" },
	chart_of_accounts: { icon: "chart", tone: "blue" },
	project_account_mapping: { icon: "link", tone: "violet" },
};

// "dashboard" stacks rows in a panel; "tiles" lays the same rows out in a grid.
const panel = computed(() => props.variant === "dashboard" || props.variant === "tiles");

function visualFor(id) {
	return actionVisuals[id] || { icon: "spark", tone: "slate" };
}
</script>

<style scoped>
.action-panel {
	border: 1px solid var(--line);
	border-radius: var(--radius-card);
	background: var(--surface);
	box-shadow: var(--shadow-soft);
}
.text-ink-2 { color: var(--ink-2); }
/* Tones stay as names (tests and data use them) but share one quiet, navy-friendly palette. */
.action-icon--blue { background: var(--navy-50); color: var(--navy-900); }
.action-icon--green { background: #e8f3ee; color: #1e6b47; }
.action-icon--amber { background: var(--marigold-soft); color: #8a5300; }
.action-icon--violet { background: #f0edf7; color: #574585; }
.action-icon--cyan { background: #e7f1f5; color: #1d5a72; }
.action-icon--slate { background: var(--soft); color: #46546a; }
</style>
