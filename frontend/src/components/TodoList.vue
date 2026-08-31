<template>
	<section v-if="items.length">
		<div class="flex items-center justify-between mb-3">
			<h2 class="text-sm font-semibold text-ink flex items-center gap-2">
				<Icon :name="icon" size="sm" :class="iconClass" />
				{{ title }}
				<span
					class="min-w-[1.25rem] h-5 px-1.5 rounded-full bg-todo-soft text-todo text-xs font-bold inline-flex items-center justify-center"
					>{{ totalCount }}</span
				>
			</h2>
			<RouterLink
				v-if="seeAllTo && totalCount > items.length"
				:to="seeAllTo"
				class="text-sm text-accent hover:underline"
			>
				{{ seeAllLabel || `See all ${totalCount}` }}
			</RouterLink>
			<RouterLink
				v-else-if="seeAllTo && seeAllAlways"
				:to="seeAllTo"
				class="text-sm text-accent hover:underline"
			>
				{{ seeAllLabel || "See all" }}
			</RouterLink>
		</div>
		<ul class="rounded-2xl border border-line bg-surface shadow-soft divide-y divide-line overflow-hidden">
			<li v-for="item in items" :key="item.id">
				<a
					:href="item.route"
					class="flex items-start gap-3 px-4 py-3.5 hover:bg-accent-soft transition-colors duration-150 active:scale-[0.99]"
				>
					<span
						:class="
							cn(
								'mt-0.5 w-9 h-9 rounded-xl flex items-center justify-center shrink-0',
								bucketClass(item.bucket)
							)
						"
					>
						<Icon :name="bucketIcon(item.bucket)" />
					</span>
					<div class="min-w-0 flex-1">
						<div class="text-[11px] font-semibold uppercase tracking-wide text-muted">{{ item.kind }}</div>
						<div class="font-medium text-ink truncate">{{ item.title }}</div>
						<div class="text-sm text-muted truncate">{{ item.subtitle }}</div>
					</div>
					<span class="text-sm font-medium text-accent shrink-0 mt-3">Open</span>
				</a>
			</li>
		</ul>
	</section>
	<section v-else-if="showEmpty" class="rounded-2xl border border-dashed border-line bg-surface p-6 text-center">
		<Icon name="spark" class="mx-auto text-ok mb-2" size="lg" />
		<h2 class="text-sm font-semibold text-ink">{{ emptyTitle || title }}</h2>
		<p class="text-sm text-muted mt-1">{{ emptyHint }}</p>
	</section>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import Icon from "./Icon.vue";
import { cn } from "../lib/cn";

const props = defineProps({
	title: { type: String, default: "Waiting on you" },
	icon: { type: String, default: "check" },
	iconClass: { type: String, default: "text-todo" },
	items: { type: Array, default: () => [] },
	totalCount: { type: Number, default: undefined },
	seeAllTo: { type: String, default: "" },
	seeAllLabel: { type: String, default: "" },
	seeAllAlways: { type: Boolean, default: false },
	showEmpty: { type: Boolean, default: false },
	emptyTitle: { type: String, default: "" },
	emptyHint: { type: String, default: "Nothing waiting. You’re clear." },
});

const totalCount = computed(() =>
	props.totalCount === undefined ? props.items.length : props.totalCount
);

function bucketClass(bucket) {
	if (bucket === "pay") return "bg-warn-soft text-warn";
	if (bucket === "resume" || bucket === "yours") return "bg-soft text-muted";
	return "bg-todo-soft text-todo";
}

function bucketIcon(bucket) {
	if (bucket === "pay") return "wallet";
	if (bucket === "resume" || bucket === "yours") return "clock";
	return "check";
}
</script>
