export function cn(...parts) {
	const names = [];
	for (const part of parts.flat()) {
		if (!part) continue;
		if (typeof part === "string") {
			names.push(part);
			continue;
		}
		if (typeof part === "object") {
			for (const [name, on] of Object.entries(part)) {
				if (on) names.push(name);
			}
		}
	}
	return names.join(" ").replace(/\s+/g, " ").trim();
}
