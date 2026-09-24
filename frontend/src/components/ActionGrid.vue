<template>
	<div v-if="actions.length">
		<h2 class="text-sm font-semibold text-ink mb-2 flex items-center gap-2">
			<Icon :name="icon" size="sm" class="text-accent" />
			{{ title }}
		</h2>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
			<article
				v-for="action in actions"
				:key="action.id"
				:data-action-id="action.id"
				class="rounded-2xl border border-line bg-surface p-3 shadow-soft hover:shadow-lift hover:-translate-y-0.5 transition-all duration-200"
			>
				<a :href="action.route" class="group flex items-start gap-3 p-1">
					<span
						:data-icon-name="visualFor(action.id).icon"
						:data-icon-tone="visualFor(action.id).tone"
						:class="[
							'w-10 h-10 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform duration-200',
							`action-icon--${visualFor(action.id).tone}`,
						]"
					>
						<Icon :name="visualFor(action.id).icon" />
					</span>
					<div>
						<div class="font-semibold text-ink">{{ action.label }}</div>
						<div class="text-sm text-muted mt-0.5">{{ action.hint }}</div>
					</div>
				</a>
				<a
					v-if="action.list_route"
					:href="action.list_route"
					class="mt-2 self-start inline-flex items-center gap-2 rounded-full bg-soft px-2.5 py-1 text-xs text-muted hover:shadow-soft hover:-translate-y-px transition-all duration-150"
				>
					<span>{{ action.list_label }}</span>
					<span class="tabular-nums font-semibold text-ink">{{
						action.pending || 0
					}}</span>
				</a>
			</article>
		</div>
	</div>
</template>

<script setup>
import Icon from "./Icon.vue";

defineProps({
	title: { type: String, required: true },
	icon: { type: String, default: "spark" },
	actions: { type: Array, default: () => [] },
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
	vendor: { icon: "vendor", tone: "violet" },
	advance: { icon: "coins", tone: "blue" },
	claim: { icon: "receipt", tone: "amber" },
	invoice_generator: { icon: "invoice", tone: "cyan" },
	bank_account: { icon: "bank", tone: "green" },
	office_addresses: { icon: "map-pin", tone: "cyan" },
	how_to_spend: { icon: "guide", tone: "slate" },
	advance_disbursement: { icon: "money-out", tone: "blue" },
	advance_returns: { icon: "money-return", tone: "amber" },
	chart_of_accounts: { icon: "chart", tone: "blue" },
	project_account_mapping: { icon: "link", tone: "violet" },
};

function visualFor(id) {
	return actionVisuals[id] || { icon: "spark", tone: "slate" };
}
</script>

<style scoped>
.action-icon--blue {
	background: #e7f0ff;
	color: #2b63ad;
}

.action-icon--green {
	background: #e1f3e8;
	color: #237653;
}

.action-icon--amber {
	background: #fff0d3;
	color: #956000;
}

.action-icon--violet {
	background: #efe8ff;
	color: #6b4ca5;
}

.action-icon--cyan {
	background: #dff3f2;
	color: #176f73;
}

.action-icon--slate {
	background: #e9eef1;
	color: #4d626e;
}

:global(html.dark) .action-icon--blue {
	background: rgb(96 165 250 / 0.16);
	color: #93c5fd;
}

:global(html.dark) .action-icon--green {
	background: rgb(74 222 128 / 0.14);
	color: #86d9a3;
}

:global(html.dark) .action-icon--amber {
	background: rgb(245 158 11 / 0.15);
	color: #e8ba69;
}

:global(html.dark) .action-icon--violet {
	background: rgb(167 139 250 / 0.15);
	color: #c4aff7;
}

:global(html.dark) .action-icon--cyan {
	background: rgb(34 211 238 / 0.13);
	color: #7ccbd0;
}

:global(html.dark) .action-icon--slate {
	background: rgb(148 163 184 / 0.14);
	color: #aab7c2;
}
</style>
