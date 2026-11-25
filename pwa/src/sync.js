import { request, PWA_API, session } from "./api.js";
import { activeAccount, outbox, write, remove, clearSnapshots, withQueueLock } from "./storage.js";
import { queueFailure } from "./model.js";

export async function flush(user, changed = () => {}) {
	return withQueueLock(user, async (renew) => {
		if ((await activeAccount()) !== user) return;
		const current = await session();
		if (!current.allowed || current.user !== user) {
			await clearSnapshots(user);
			throw Object.assign(
				new Error("Sign in to the original account to send these changes."),
				{ status: 401 },
			);
		}
		for (const row of await outbox(user)) {
			if (row.status !== "pending") continue;
			if ((await activeAccount()) !== user || !(await renew())) return;
			// Stop later operations on the same record if an earlier change needs attention.
			const target = row.payload.name || row.payload.space || row.payload.payload?.space;
			if (
				(await outbox(user)).some(
					(prior) =>
						prior.created < row.created &&
						prior.status === "attention" &&
						(prior.payload.name ||
							prior.payload.space ||
							prior.payload.payload?.space) === target,
				)
			)
				continue;
			try {
				const result = await request(PWA_API + "apply_operation", {
					method: row.method,
					payload: row.payload,
					request_key: row.id,
					expected_user: user,
				});
				await remove(user, `queue:${row.id}`);
				await changed(row, result);
			} catch (error) {
				const kind = queueFailure(error);
				if (kind === "retry" || kind === "auth") throw error;
				if (kind === "denied") await clearSnapshots(user);
				await write(user, `queue:${row.id}`, {
					...row,
					status: "attention",
					error: error.message,
				});
				await changed(row);
			}
		}
	});
}
