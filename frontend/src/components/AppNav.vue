<template>
	<nav
		:class="cn('flex', layout === 'bottom' ? 'justify-center gap-8' : 'gap-2 flex-wrap')"
		:aria-label="ariaLabel"
	>
		<RouterLink
			v-for="item in items"
			:key="item.to"
			:to="item.to"
			:aria-label="item.label"
			:class="
				cn(
					'relative flex items-center gap-1.5 rounded-2xl text-sm font-medium transition-all duration-150',
					layout === 'bottom'
						? 'flex-col py-2 px-3 text-[11px] text-muted'
						: 'px-3 py-1.5 text-muted hover:text-ink hover:bg-accent-soft',
					{ 'text-accent': isActive(item.to) }
				)
			"
			active-class=""
		>
			<span
				:class="
					cn(
						'flex items-center justify-center rounded-2xl transition-transform duration-150',
						layout === 'bottom' ? 'w-10 h-8' : '',
						isActive(item.to) && layout === 'bottom' ? 'bg-accent-soft scale-105' : '',
						isActive(item.to) && layout !== 'bottom' ? 'text-accent' : ''
					)
				"
			>
				<Icon :name="item.icon" :size="layout === 'bottom' ? 'md' : 'sm'" />
			</span>
			<span>{{ item.label }}</span>
			<span
				v-if="item.badge"
				class="absolute top-1 right-1/4 md:static md:ml-1 min-w-[1.1rem] h-4 px-1 rounded-full bg-todo text-on-todo text-[10px] font-bold inline-flex items-center justify-center"
				>{{ item.badge > 9 ? "9+" : item.badge }}</span
			>
		</RouterLink>
	</nav>
</template>

<script setup>
import { RouterLink, useRoute } from "vue-router";
import Icon from "./Icon.vue";
import { cn } from "../lib/cn";

defineProps({
	items: { type: Array, required: true },
	layout: { type: String, default: "top" },
	ariaLabel: { type: String, default: "Primary" },
});

const route = useRoute();

function isActive(to) {
	if (to === "/home") {
		return route.path === "/home" || route.path === "/";
	}
	return route.path === to || route.path.startsWith(`${to}/`);
}
</script>
