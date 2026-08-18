module.exports = {
	content: ["./index.html", "./src/**/*.{vue,js}"],
	theme: {
		extend: {
			colors: {
				bg: "var(--bg)",
				surface: "var(--surface)",
				soft: "var(--soft)",
				ink: "var(--ink)",
				muted: "var(--muted)",
				line: "var(--line)",
				accent: "var(--accent)",
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
			},
			borderColor: {
				DEFAULT: "var(--line)",
			},
			boxShadow: {
				soft: "var(--shadow-soft)",
				lift: "var(--shadow-lift)",
			},
		},
	},
	plugins: [],
};
