<template>
	<section v-if="links.length">
		<h2 class="text-sm font-semibold text-ink mb-2 flex items-center gap-2">
			<Icon :name="icon" size="sm" class="text-accent" />
			{{ title }}
		</h2>
		<div class="flex flex-wrap gap-2">
			<a
				v-for="link in links"
				:key="link.id"
				:href="link.route"
				class="px-3 py-2 rounded-xl border border-line bg-surface text-sm text-ink hover:bg-soft transition-all duration-150"
			>
				{{ link.label }}
				<span v-if="link.count" class="font-semibold text-todo ml-1">{{ link.count }}</span>
			</a>
		</div>
	</section>
</template>

<script setup>
import Icon from "./Icon.vue";

defineProps({
	title: { type: String, required: true },
	icon: { type: String, default: "spark" },
	links: { type: Array, default: () => [] },
});
</script>
