// Only SF Tasks PWA uses this database. Private content is never placed in the HTTP cache.
const DATABASE = "sf-tasks-pwa-v1";
let opening;
export function database() {
	return (opening ||= new Promise((resolve, reject) => {
		const request = indexedDB.open(DATABASE, 1);
		request.onupgradeneeded = () => {
			for (const name of ["accounts", "records", "meta", "leases"])
				request.result.createObjectStore(name, { keyPath: "id" });
		};
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => {
			opening = null;
			reject(request.error);
		};
	}));
}
async function transact(store, mode, action) {
	const db = await database();
	return new Promise((resolve, reject) => {
		const tx = db.transaction(store, mode);
		let value;
		const operation = action(tx.objectStore(store));
		if (operation)
			operation.onsuccess = () => {
				value = operation.result;
			};
		tx.oncomplete = () => resolve(value);
		tx.onerror = () => reject(tx.error);
		tx.onabort = () => reject(tx.error || new Error("Local storage is unavailable."));
	});
}
export async function activeAccount() {
	return (await transact("meta", "readonly", (store) => store.get("active")))?.value || null;
}
export async function activate(user) {
	let account = await transact("accounts", "readonly", (store) => store.get(user));
	if (!account) {
		account = {
			id: user,
			key: await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, [
				"encrypt",
				"decrypt",
			]),
		};
		await transact("accounts", "readwrite", (store) => store.put(account));
	}
	await transact("meta", "readwrite", (store) => store.put({ id: "active", value: user }));
	return user;
}
async function keyFor(user) {
	const account = await transact("accounts", "readonly", (store) => store.get(user));
	if (!account) throw new Error("Sign in before saving work on this device.");
	return account.key;
}
export async function write(user, key, value) {
	const iv = crypto.getRandomValues(new Uint8Array(12)),
		name = `${user}:${key}`;
	const data = await crypto.subtle.encrypt(
		{ name: "AES-GCM", iv, additionalData: new TextEncoder().encode(name) },
		await keyFor(user),
		new TextEncoder().encode(JSON.stringify(value)),
	);
	await transact("records", "readwrite", (store) =>
		store.put({ id: name, user, key, iv, data }),
	);
}
export async function read(user, key) {
	const row = await transact("records", "readonly", (store) => store.get(`${user}:${key}`));
	if (!row) return null;
	const data = await crypto.subtle.decrypt(
		{ name: "AES-GCM", iv: row.iv, additionalData: new TextEncoder().encode(row.id) },
		await keyFor(user),
		row.data,
	);
	return JSON.parse(new TextDecoder().decode(data));
}
export const remove = (user, key) =>
	transact("records", "readwrite", (store) => store.delete(`${user}:${key}`));
export async function list(user, prefix) {
	const rows = await transact("records", "readonly", (store) => store.getAll());
	return Promise.all(
		rows
			.filter((row) => row.user === user && row.key.startsWith(prefix))
			.map((row) => read(user, row.key)),
	);
}
export async function forget(user) {
	const rows = await transact("records", "readonly", (store) => store.getAll());
	for (const row of rows.filter((row) => row.user === user))
		await transact("records", "readwrite", (store) => store.delete(row.id));
	await transact("accounts", "readwrite", (store) => store.delete(user));
	if ((await activeAccount()) === user)
		await transact("meta", "readwrite", (store) => store.delete("active"));
}
export async function clearSnapshots(user) {
	const rows = await transact("records", "readonly", (store) => store.getAll());
	for (const row of rows.filter(
		(row) =>
			row.user === user &&
			/^(home|work|room:|item:|item-view:|comments:|files:|file:|history:|mentions)/.test(
				row.key,
			),
	))
		await remove(user, row.key);
}
export async function enqueue(user, method, payload, clearDraft = null) {
	const row = {
		id: crypto.randomUUID(),
		method,
		payload,
		created: Date.now(),
		status: "pending",
		error: "",
	};
	const entries = [[`queue:${row.id}`, row], ...(clearDraft ? [[clearDraft, ""]] : [])];
	const key = await keyFor(user),
		encoded = [];
	for (const [name, value] of entries) {
		const recordId = `${user}:${name}`,
			iv = crypto.getRandomValues(new Uint8Array(12));
		const data = await crypto.subtle.encrypt(
			{ name: "AES-GCM", iv, additionalData: new TextEncoder().encode(recordId) },
			key,
			new TextEncoder().encode(JSON.stringify(value)),
		);
		encoded.push({ id: recordId, user, key: name, iv, data });
	}
	const db = await database();
	await new Promise((resolve, reject) => {
		const tx = db.transaction("records", "readwrite");
		for (const record of encoded) tx.objectStore("records").put(record);
		tx.oncomplete = resolve;
		tx.onerror = () => reject(tx.error);
		tx.onabort = () => reject(tx.error);
	});
	return row;
}
export async function outbox(user) {
	return (await list(user, "queue:")).sort((a, b) => a.created - b.created);
}
async function lease(user, owner) {
	const db = await database();
	return new Promise((resolve, reject) => {
		const tx = db.transaction("leases", "readwrite"),
			store = tx.objectStore("leases");
		let acquired = false;
		const req = store.get(user);
		req.onsuccess = () => {
			if (!req.result || req.result.expires < Date.now() || req.result.owner === owner) {
				store.put({ id: user, owner, expires: Date.now() + 60000 });
				acquired = true;
			}
		};
		tx.oncomplete = () => resolve(acquired);
		tx.onerror = () => reject(tx.error);
	});
}
export async function withQueueLock(user, action) {
	const owner = crypto.randomUUID();
	if (!(await lease(user, owner))) return;
	try {
		return await action(() => lease(user, owner));
	} finally {
		const db = await database();
		await new Promise((resolve, reject) => {
			const tx = db.transaction("leases", "readwrite"),
				store = tx.objectStore("leases"),
				request = store.get(user);
			request.onsuccess = () => {
				if (request.result?.owner === owner) store.delete(user);
			};
			tx.oncomplete = resolve;
			tx.onerror = () => reject(tx.error);
		});
	}
}
