const STORAGE_KEY = "volunteering.theme";

export function isDark() {
	return document.documentElement.classList.contains("dark");
}

export function initTheme() {
	const stored = localStorage.getItem(STORAGE_KEY);
	const dark =
		stored === "dark" ||
		(stored !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
	document.documentElement.classList.toggle("dark", dark);
	return dark;
}

export function toggleTheme() {
	const next = !isDark();
	document.documentElement.classList.toggle("dark", next);
	localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
	return next;
}
