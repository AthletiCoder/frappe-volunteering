<template>
	<div class="page-header mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between md:mb-8">
		<div class="min-w-0">
			<p v-if="eyebrow" class="eyebrow mb-1.5">{{ eyebrow }}</p>
			<h1 class="text-2xl font-semibold tracking-tight text-ink">{{ title }}</h1>
			<p v-if="subtitle" class="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-muted">{{ subtitle }}</p>
		</div>
		<div v-if="$slots.actions" class="page-header-actions flex shrink-0 flex-wrap items-center gap-2">
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
