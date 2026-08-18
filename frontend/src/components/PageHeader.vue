<template>
	<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-6">
		<div class="min-w-0">
			<p v-if="eyebrow" class="text-xs font-semibold uppercase tracking-wide text-muted mb-1">{{ eyebrow }}</p>
			<h1 class="text-2xl font-bold text-ink tracking-tight">{{ title }}</h1>
			<p v-if="subtitle" class="text-sm text-muted mt-1 max-w-2xl">{{ subtitle }}</p>
		</div>
		<div v-if="$slots.actions" class="flex flex-wrap gap-2 shrink-0">
			<slot name="actions" />
		</div>
	</div>
</template>

<script setup>
defineProps({
	eyebrow: { type: String, default: "" },
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
});
</script>
