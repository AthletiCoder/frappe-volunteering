const STORAGE_KEY = "volunteering.theme";

export function isDark() {
	return document.documentElement.classList.contains("dark");
}

export function initTheme() {
	document.documentElement.classList.remove("dark");
	document.documentElement.style.colorScheme = "light";
	localStorage.setItem(STORAGE_KEY, "light");
	return false;
}

export function toggleTheme() {
	// Keep the theme API available for future use, but the employee portal is
	// intentionally locked to light mode for now.
	return initTheme();
}
