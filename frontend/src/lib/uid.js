// crypto.randomUUID only exists in secure contexts (HTTPS or localhost).
// Sites served over plain http on a LAN hostname still need unique keys, so
// fall back to an RFC 4122 v4 id built from crypto.getRandomValues.
export function uid() {
	const c = globalThis.crypto;
	if (c?.randomUUID) return c.randomUUID();
	const bytes = new Uint8Array(16);
	if (c?.getRandomValues) c.getRandomValues(bytes);
	else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
