<template>
	<section v-if="programs">
		<h2 class="text-sm font-semibold text-ink mb-2 flex items-center gap-2">
			<Icon name="spark" size="sm" class="text-ok" />
			Programs
		</h2>
		<div
			class="rounded-2xl border border-line bg-surface p-4 shadow-soft flex flex-col sm:flex-row sm:flex-wrap gap-4 sm:items-center sm:justify-between"
		>
			<div>
				<div class="text-xs text-muted">Latest campaign</div>
				<div class="font-semibold text-ink">{{ programs.event || "No campaign yet" }}</div>
				<div class="text-sm text-muted mt-1">{{ programs.registrations }} registrations</div>
			</div>
			<div class="flex gap-2">
				<a class="btn-secondary text-sm" :href="programs.workspace_route">Campaign dashboard</a>
				<a class="btn-primary text-sm" :href="programs.report_route">Event report</a>
			</div>
		</div>
	</section>
</template>

<script setup>
import Icon from "./Icon.vue";

defineProps({
	programs: { type: Object, default: null },
});
</script>
