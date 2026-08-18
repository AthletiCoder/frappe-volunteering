import { ref } from "vue";
import { call } from "./frappe";
import { maybeNotifyNewTodos } from "./notify";

export const homePayload = ref(null);

export async function loadHomePayload({ notify = true } = {}) {
	const payload = await call("volunteering.volunteering.home_service.get_home_payload");
	if (notify) {
		maybeNotifyNewTodos(payload);
	}
	homePayload.value = payload;
	return payload;
}

let pollTimer = null;

export function startHomePoll(ms = 45000) {
	stopHomePoll();
	pollTimer = setInterval(() => {
		loadHomePayload({ notify: true }).catch(() => {});
	}, ms);
}

export function stopHomePoll() {
	if (pollTimer) {
		clearInterval(pollTimer);
		pollTimer = null;
	}
}
