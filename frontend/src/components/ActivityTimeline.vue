<template>
	<ol class="activity">
		<li v-for="(event, index) in events" :key="`${event.meta}-${index}`" class="activity__item" :class="{ 'activity__item--latest': index === latestIndex }">
			<span class="activity__dot" aria-hidden="true"></span>
			<div class="min-w-0">
				<strong class="block text-sm text-ink">{{ event.label }}</strong>
				<p v-if="event.meta" class="mt-0.5 text-xs text-muted">{{ event.meta }}</p>
				<p v-if="event.detail" class="mt-1 whitespace-pre-wrap text-[13px] text-ink-2 [overflow-wrap:anywhere]">{{ event.detail }}</p>
			</div>
		</li>
	</ol>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	events: { type: Array, default: () => [] },
	// Which end of the list is the most recent event.
	latest: { type: String, default: "last" },
});
const latestIndex = computed(() => (props.latest === "first" ? 0 : props.events.length - 1));
</script>

<style scoped>
.activity { display: grid; }
.activity__item { position: relative; display: flex; gap: 0.75rem; padding-bottom: 1rem; }
.activity__item:last-child { padding-bottom: 0; }
.activity__item:not(:last-child)::before { content: ""; position: absolute; left: 0.3125rem; top: 1rem; bottom: 0; width: 1px; background: var(--line); }
.activity__dot { position: relative; z-index: 1; margin-top: 0.3rem; width: 0.6875rem; height: 0.6875rem; flex-shrink: 0; border-radius: 999px; border: 2px solid var(--line-strong); background: var(--surface); }
.activity__item--latest .activity__dot { border-color: var(--navy-900); background: var(--navy-900); box-shadow: 0 0 0 3px var(--navy-50); }
.text-ink-2 { color: var(--ink-2); }
</style>
