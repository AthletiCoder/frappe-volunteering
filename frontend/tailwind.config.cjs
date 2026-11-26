module.exports = {
	content: ["./index.html", "./src/**/*.{vue,js}"],
	// The portal is light-only; never let an OS dark preference flip `dark:` utilities.
	darkMode: "class",
	theme: {
		extend: {
			fontFamily: {
				sans: ["Inter Variable", "Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
				display: ["Poppins", "Inter Variable", "ui-sans-serif", "system-ui", "sans-serif"],
			},
			colors: {
				bg: "var(--bg)",
				surface: "var(--surface)",
				soft: "var(--soft)",
				ink: "var(--ink)",
				muted: "var(--muted)",
				line: "var(--line)",
				"line-strong": "var(--line-strong)",
				accent: "var(--accent)",
				"accent-hover": "var(--accent-hover)",
				"accent-soft": "var(--accent-soft)",
				"on-accent": "var(--on-accent)",
				todo: "var(--todo)",
				"todo-soft": "var(--todo-soft)",
				"on-todo": "var(--on-todo)",
				ok: "var(--ok)",
				"ok-soft": "var(--ok-soft)",
				warn: "var(--warn)",
				"warn-soft": "var(--warn-soft)",
				bad: "var(--bad)",
				"bad-soft": "var(--bad-soft)",
				navy: {
					50: "var(--navy-50)",
					100: "var(--navy-100)",
					200: "var(--navy-200)",
					600: "var(--navy-600)",
					800: "var(--navy-800)",
					900: "var(--navy-900)",
				},
				marigold: {
					DEFAULT: "var(--marigold)",
					soft: "var(--marigold-soft)",
				},
			},
			borderColor: {
				DEFAULT: "var(--line)",
			},
			boxShadow: {
				soft: "var(--shadow-soft)",
				lift: "var(--shadow-lift)",
				pop: "var(--shadow-pop)",
			},
			transitionTimingFunction: {
				out: "cubic-bezier(.2,.8,.2,1)",
			},
		},
	},
	plugins: [],
};
