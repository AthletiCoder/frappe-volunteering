<template>
	<div class="space-y-6">
		<PageHeader
			title="Review pending proposals"
			subtitle="Review project proposals and change requests that are awaiting a Projects Manager."
			eyebrow="Projects"
		>
			<template #actions>
				<RouterLink to="/projects?view=approved" class="btn-secondary"
					>Approved projects</RouterLink
				>
				<RouterLink to="/home" class="btn-secondary">Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="loading" class="text-muted" role="status">Loading pending proposals…</p>
		<p v-else-if="error" class="message-error" role="alert">{{ error }}</p>

		<section v-else class="form-card">
			<div class="flex flex-wrap items-end justify-between gap-3">
				<div>
					<h2 class="form-title mb-0">Pending review</h2>
					<p class="form-hint mt-1">
						All Projects Managers can see these pending requests. Only the manager
						selected by the proposer can edit or decide a request.
					</p>
				</div>
				<span class="project-badge">{{ pendingProposals.length }} pending</span>
			</div>

			<p v-if="!pendingProposals.length" class="text-sm text-muted mt-5">
				No project proposals are awaiting review.
			</p>
			<button
				v-for="item in pendingProposals"
				:key="item.name"
				type="button"
				class="project-tile block w-full text-left mt-3"
				@click="openProposal(item.name)"
			>
				<div class="flex flex-wrap justify-between gap-2">
					<span class="project-badge">Pending Approval</span>
					<span v-if="item.assigned_approver === currentUser" class="project-badge"
						>Assigned to you</span
					>
				</div>
				<strong class="block mt-2">{{ item.title }}</strong>
				<span class="text-xs text-muted">
					{{ item.request_kind }} · Proposed by {{ item.proposed_by }} · Assigned to
					{{ item.assigned_approver }}
				</span>
			</button>
		</section>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const workspaceMethod = "volunteering.volunteering.project_workspace.";
const proposalMethod = "volunteering.volunteering.project_proposals.";
const router = useRouter();
const loading = ref(true);
const error = ref("");
const proposals = ref([]);
const capabilities = ref({});
const currentUser = computed(() => capabilities.value.current_user || "");
const pendingProposals = computed(() =>
	proposals.value.filter(
		(item) =>
			item.proposal_status === "Pending Approval" && item.proposed_by !== currentUser.value,
	),
);

function openProposal(proposal) {
	router.push({
		path: "/projects",
		query: { proposal, returnTo: "pending-proposals" },
	});
}

onMounted(async () => {
	try {
		const projects = await call(workspaceMethod + "get_projects");
		capabilities.value = projects.capabilities || {};
		if (!capabilities.value.can_manage) {
			throw new Error("Only Projects Managers can review project proposals.");
		}
		proposals.value = await call(proposalMethod + "get_proposals");
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
});
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-5 md:p-6 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted mb-4 leading-relaxed;
}
.project-tile {
	@apply rounded-2xl border border-line bg-surface p-5 shadow-soft transition-all hover:shadow-lift hover:border-accent break-words;
}
.project-badge {
	@apply text-xs px-2.5 py-1 rounded-full bg-accent-soft text-accent font-medium shrink-0;
}
.message-error {
	@apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad;
}
</style>
