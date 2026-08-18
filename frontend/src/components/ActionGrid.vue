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
				class="rounded-2xl border border-line bg-surface p-3 shadow-soft hover:shadow-lift hover:-translate-y-0.5 transition-all duration-200"
			>
				<a :href="action.route" class="group flex items-start gap-3 p-1">
					<span
						class="w-10 h-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center group-hover:scale-110 transition-transform duration-200"
					>
						<Icon :name="iconFor(action.id)" />
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
					<span class="tabular-nums font-semibold text-ink">{{ action.pending || 0 }}</span>
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

function iconFor(id) {
	const map = {
		log_work: "clock",
		wfh: "sun",
		leave: "leave",
		fix_attendance: "fix",
		vendor: "vendor",
		advance: "advance",
		claim: "claim",
		how_to_spend: "book",
	};
	return map[id] || "spark";
}
</script>
