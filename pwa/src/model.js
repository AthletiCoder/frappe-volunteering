export const OPEN = new Set(["Open", "In progress"]);
export const id = () => crypto.randomUUID();
export const copy = (value) => JSON.parse(JSON.stringify(value));
export function pendingWith(item) {
	if (!OPEN.has(item.status)) return null;
	const d = item.item_data || {};
	if (d.assignment_mode === "Stages") {
		const stage = (d.stages || []).find((row) => row.key === d.stage) || d.stages?.[0];
		return stage ? { user: stage.assignee, full_name: stage.assignee_name } : null;
	}
	return { user: item.assignee || item.owner, full_name: item.assignee_name || item.owner };
}
export function progressOf(item) {
	const d = item.item_data || {};
	if (["Status", "Stages"].includes(d.scale)) {
		const stages = d.stages || [],
			index = stages.findIndex((row) => row.key === d.stage);
		return {
			label: stages[index]?.label || "Not started",
			percent:
				item.status === "Completed"
					? 100
					: index < 0
						? 0
						: d.scale === "Stages"
							? Number(stages[index].position)
							: stages.length < 2
								? 0
								: (index / (stages.length - 1)) * 100,
			stages,
			index,
		};
	}
	const value = d.value,
		low = Number(d.minimum || 0),
		high = Number(d.maximum || 100);
	return {
		label:
			value == null
				? "Not started"
				: `${value}${d.scale === "Percentage" ? "%" : ` ${d.unit || ""}`}`,
		percent:
			item.status === "Completed"
				? 100
				: value == null
					? 0
					: Math.max(0, Math.min(100, ((value - low) / (high - low)) * 100)),
		stages: [],
		index: -1,
	};
}
export function trackerState(item) {
	return item.status === "Completed"
		? "complete"
		: OPEN.has(item.status)
			? progressOf(item).percent > 0 || item.item_data?.stage
				? "progress"
				: "waiting"
			: "closed";
}
export function receipt(entry, room) {
	const cursor = room?.receipt_through || {};
	return cursor.seen_through && cursor.seen_through >= entry.creation
		? 3
		: cursor.delivered_through && cursor.delivered_through >= entry.creation
			? 2
			: 1;
}
export function prettyDate(value, withTime = false) {
	if (!value) return "";
	const date = new Date(String(value).replace(" ", "T"));
	return Number.isNaN(date.getTime())
		? value
		: date.toLocaleString(undefined, {
				day: "numeric",
				month: "short",
				...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
			});
}
export function safeFileURL(value, origin = globalThis.location?.origin) {
	try {
		const url = new URL(value, origin);
		return url.origin === origin && url.pathname.startsWith("/private/files/")
			? url.pathname + url.search
			: null;
	} catch {
		return null;
	}
}
export function queueFailure(error) {
	if (error.status === 401) return "auth";
	if (error.status === 403) return "denied";
	if (!error.status || error.status >= 500 || [408, 429].includes(error.status)) return "retry";
	return "attention";
}
export function filterTrackers(items, filter, user) {
	return items.filter((item) =>
		filter === "All" || filter === "Completed"
			? filter === "All" || item.status === "Completed"
			: OPEN.has(item.status) &&
				(filter === "Open" ||
					(pendingWith(item)?.user === user) === (filter === "My actions")),
	);
}
export function newItem(kind, user, source) {
	return {
		item_kind: kind,
		title: source?.body?.slice(0, 160) || "",
		description: "",
		source_entry: source?.name || null,
		assignee: user,
		priority: "Medium",
		repeat_pattern: "None",
		participants: [],
		item_data:
			kind === "Tracker"
				? {
						scale: "Status",
						assignment_mode: "Single",
						stages: [],
						stage: null,
						next_action: "",
					}
				: kind === "Task"
					? { subtasks: [] }
					: kind === "List"
						? { rows: [] }
						: {},
	};
}
export function itemPayload(form) {
	const fields = [
		"title",
		"item_kind",
		"description",
		"source_entry",
		"assignee",
		"priority",
		"from_date",
		"until_date",
		"deadline",
		"snoozed_until",
		"repeat_pattern",
		"repeat_until",
		"start_at",
		"end_at",
		"location",
		"participants",
		"item_data",
	];
	return Object.fromEntries(
		fields
			.filter((key) => form[key] !== undefined)
			.map((key) => [key, form[key] === "" ? null : copy(form[key])]),
	);
}

export function mergeConversation(previous, incoming) {
	if (!previous || previous.space.name !== incoming.space.name || !previous.entries.length)
		return incoming;
	const entries = new Map(previous.entries.map((entry) => [entry.name, entry]));
	for (const entry of incoming.entries) entries.set(entry.name, entry);
	const ordered = [...entries.values()].sort(
		(a, b) => a.creation.localeCompare(b.creation) || a.name.localeCompare(b.name),
	);
	const keptOlder =
		incoming.entries.length && previous.entries[0].creation < incoming.entries[0].creation;
	return {
		...incoming,
		entries: ordered.slice(-500),
		older_cursor:
			ordered.length > 500
				? ordered.at(-500).name
				: keptOlder
					? previous.older_cursor
					: incoming.older_cursor,
	};
}
