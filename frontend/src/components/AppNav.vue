<template>
	<nav
		:class="cn('flex', layout === 'bottom' ? 'w-full justify-around gap-0.5' : layout === 'sidebar' ? 'w-full flex-col gap-0.5' : 'gap-0.5')"
		:aria-label="ariaLabel"
	>
		<template v-for="item in items" :key="itemKey(item)">
			<p v-if="item.section && layout === 'sidebar'" class="eyebrow px-3 pb-1.5 pt-6 first:pt-2">{{ item.section }}</p>
			<details v-else-if="item.children && layout === 'sidebar'" :open="item.children.some((child) => isActiveHref(child.href))" class="nav-group group">
				<summary :class="cn(linkClass(item, item.children.some((child) => isActiveHref(child.href))), 'record-summary cursor-pointer list-none select-none')">
					<span :class="iconWrapClass(item, item.children.some((child) => isActiveHref(child.href)))"><Icon :name="item.icon" size="sm" /></span>
					<span class="min-w-0 flex-1">{{ item.label }}</span>
					<Icon name="chevron-down" size="sm" class="ml-auto text-muted/70 transition-transform duration-200 ease-out group-open:rotate-180" />
				</summary>
				<div class="relative mb-1 ml-[1.35rem] mt-0.5 space-y-0.5 border-l border-line pl-2.5">
					<a v-for="child in item.children" :key="child.href" :href="child.href" :title="child.label" :aria-current="isActiveHref(child.href) ? 'page' : undefined" :class="cn('relative flex min-h-[2.125rem] items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px] text-muted transition-colors duration-150 hover:bg-soft hover:text-ink', { 'nav-child-active bg-navy-50 font-semibold text-navy-900': isActiveHref(child.href) })" @click="emit('navigate')">
						<span class="min-w-0 flex-1 leading-snug">{{ child.label }}</span>
						<span v-if="child.badge" class="shrink-0 rounded-full bg-marigold-soft px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-todo">{{ child.badge > 9 ? '9+' : child.badge }}</span>
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
				<span :class="layout === 'bottom' ? 'max-w-full truncate' : null">{{ item.label }}</span>
				<span v-if="item.badge && layout === 'sidebar'" class="ml-auto rounded-full bg-marigold-soft px-2 py-0.5 text-xs font-semibold tabular-nums text-todo">{{ item.badge > 9 ? '9+' : item.badge }}</span>
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
				<span :class="layout === 'bottom' ? 'max-w-full truncate' : null">{{ item.label }}</span>
				<span
					v-if="item.badge"
					:class="layout === 'sidebar' ? 'ml-auto rounded-full bg-marigold-soft px-2 py-0.5 text-xs font-semibold tabular-nums text-todo' : 'absolute left-1/2 top-0.5 ml-1.5 inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full bg-marigold px-1 text-[10px] font-bold text-on-todo ring-2 ring-surface'"
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
		"relative flex items-center font-medium transition-colors duration-150",
		props.layout === "bottom"
			? "min-w-0 flex-1 flex-col gap-0.5 rounded-xl px-0.5 pb-1.5 pt-1 text-[11px] text-muted"
			: props.layout === "sidebar"
				? "min-h-[2.375rem] gap-3 rounded-xl px-2.5 py-2 text-sm text-ink-2 hover:bg-soft hover:text-ink"
				: "gap-3 rounded-xl px-2 py-1.5 text-sm text-muted hover:bg-accent-soft hover:text-accent",
		{
			"text-navy-900 font-semibold": active && props.layout === "bottom",
			"bg-navy-50 font-semibold text-navy-900 hover:bg-navy-50 hover:text-navy-900": active && props.layout === "sidebar",
		}
	);
}

function iconWrapClass(item, active) {
	return cn(
		"flex shrink-0 items-center justify-center transition-all duration-200 ease-out",
		props.layout === "bottom" ? "h-8 w-12 rounded-full" : "h-5 w-5 text-muted",
		active && props.layout === "bottom" ? "bg-navy-50 text-navy-900" : "",
		active && props.layout !== "bottom" ? "text-navy-900" : ""
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
.text-ink-2 { color: var(--ink-2); }
.nav-child-active::before {
	content: "";
	position: absolute;
	left: calc(-0.625rem - 1px);
	top: 0.5rem;
	bottom: 0.5rem;
	width: 2px;
	border-radius: 2px;
	background: var(--navy-900);
}
</style>
