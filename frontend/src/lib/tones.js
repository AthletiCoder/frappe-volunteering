// Status tone helpers for the shared `.pill` and `.filter-btn__dot` styles.
// Full class names are written out so Tailwind keeps them in the build.
const PILL = { ok: "pill pill--ok", warn: "pill pill--warn", bad: "pill pill--bad", info: "pill pill--info", muted: "pill pill--muted" };
const DOT = { ok: "dot--ok", warn: "dot--warn", bad: "dot--bad", info: "dot--info", muted: "dot--muted" };
export const pillClass = (tone) => PILL[tone] || PILL.muted;
export const dotClass = (tone) => DOT[tone] || DOT.muted;
