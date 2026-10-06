<template>
	<nav
		:class="cn('flex', layout === 'bottom' ? 'w-full max-w-md mx-auto justify-between gap-1' : layout === 'sidebar' ? 'w-full flex-col gap-1' : 'gap-0.5')"
		:aria-label="ariaLabel"
	>
		<template v-for="item in items" :key="itemKey(item)">
			<p v-if="item.section && layout === 'sidebar'" class="px-3 pt-5 pb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{{ item.section }}</p>
			<details v-else-if="item.children && layout === 'sidebar'" :open="item.children.some((child) => isActiveHref(child.href))" class="group">
				<summary :class="cn(linkClass(item, item.children.some((child) => isActiveHref(child.href))), 'record-summary cursor-pointer list-none')">
					<span :class="iconWrapClass(item, false)"><Icon :name="item.icon" size="sm" /></span>
					<span class="min-w-0 flex-1">{{ item.label }}</span>
					<Icon name="chevron-down" size="sm" class="ml-auto transition-transform group-open:rotate-180" />
				</summary>
				<div class="ml-5 mt-1 space-y-1 border-l border-line pl-2">
					<a v-for="child in item.children" :key="child.href" :href="child.href" :title="child.label" :aria-current="isActiveHref(child.href) ? 'page' : undefined" :class="cn('flex min-h-9 items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-muted hover:bg-soft hover:text-ink', { 'bg-accent-soft text-accent font-semibold': isActiveHref(child.href) })" @click="emit('navigate')">
						<span class="min-w-0 flex-1 truncate">{{ child.label }}</span>
						<span v-if="child.badge" class="shrink-0 rounded-full bg-soft px-1.5 py-0.5 text-[11px] tabular-nums">{{ child.badge > 9 ? '9+' : child.badge }}</span>
					</a>
				</div>
			</details>
			<a
				v-else-if="item.href"
				:href="item.href"
				:aria-label="item.label"
				:class="linkClass(item, false)"
				@click="emit('navigate')"
			>
				<span :class="iconWrapClass(item, false)">
					<Icon :name="item.icon" :size="layout === 'bottom' ? 'md' : 'sm'" />
				</span>
				<span :class="layout === 'bottom' ? 'truncate max-w-full' : null">{{ item.label }}</span>
				<span v-if="item.badge && layout === 'sidebar'" class="ml-auto rounded-full bg-todo-soft px-2 py-0.5 text-xs font-semibold text-todo">{{ item.badge > 9 ? '9+' : item.badge }}</span>
			</a>
			<RouterLink
				v-else
				:to="item.to"
				:aria-label="item.label"
				:class="linkClass(item, isActive(item.to))"
				active-class=""
				@click="emit('navigate')"
			>
				<span :class="iconWrapClass(item, isActive(item.to))">
					<Icon :name="item.icon" :size="layout === 'bottom' ? 'md' : 'sm'" />
				</span>
				<span :class="layout === 'bottom' ? 'truncate max-w-full' : null">{{ item.label }}</span>
				<span
					v-if="item.badge"
					:class="layout === 'sidebar' ? 'ml-auto rounded-full bg-todo-soft px-2 py-0.5 text-xs font-semibold text-todo' : 'absolute top-1 right-[18%] min-w-[1.1rem] h-4 px-1 rounded-full bg-todo text-on-todo text-[10px] font-bold inline-flex items-center justify-center'"
					>{{ item.badge > 9 ? "9+" : item.badge }}</span
				>
			</RouterLink>
		</template>
	</nav>
</template>

<script setup>
import { RouterLink, useRoute } from "vue-router";
import Icon from "./Icon.vue";
import { cn } from "../lib/cn";

const props = defineProps({
	items: { type: Array, required: true },
	layout: { type: String, default: "top" },
	ariaLabel: { type: String, default: "Primary" },
});
const emit = defineEmits(["navigate"]);

const route = useRoute();

function itemKey(item) {
	return item.section || item.id || item.href || item.to || item.label;
}

function isActiveHref(href) {
	if (!href?.startsWith("/volunteering/")) return false;
	const url = new URL(href, window.location.origin);
	const path = url.pathname.slice("/volunteering".length);
	if (route.path !== path && !route.path.startsWith(`${path}/`)) return false;
	return [...url.searchParams].every(([key, value]) => String(route.query[key] ?? "") === value);
}

function linkClass(item, active) {
	return cn(
		"relative flex items-center gap-2.5 text-sm font-medium transition-colors duration-150",
		props.layout === "bottom"
			? "flex-1 flex-col rounded-xl py-2 px-1 min-w-0 text-[11px] text-muted"
			: props.layout === "sidebar"
				? "min-h-10 rounded-xl px-3 py-2.5 text-muted hover:text-ink hover:bg-soft"
				: "rounded-xl px-2 py-1.5 text-muted hover:text-accent hover:bg-accent-soft",
		{ "text-accent": active && props.layout !== "sidebar", "bg-accent-soft text-accent font-semibold": active && props.layout === "sidebar" }
	);
}

function iconWrapClass(item, active) {
	return cn(
		"flex items-center justify-center rounded-2xl transition-transform duration-150",
		props.layout === "bottom" ? "w-9 h-8" : "",
		active && props.layout === "bottom" ? "bg-accent-soft scale-105" : "",
		active && props.layout !== "bottom" ? "text-accent" : ""
	);
}

function isActive(to) {
	if (!to) return false;
	if (to === "/home") {
		return route.path === "/home" || route.path === "/";
	}
	return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<style scoped>
.record-summary::-webkit-details-marker { display: none; }
</style>
