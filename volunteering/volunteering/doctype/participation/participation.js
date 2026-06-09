(function () {
	const INDIA_COUNTRY_CODE = "91";

	const sanitize_phone = (raw_phone) => {
		if (!raw_phone) return null;

		const trimmed = String(raw_phone).trim();
		const has_plus = trimmed.startsWith("+");
		const digits = trimmed.replace(/\D/g, "");

		if (!digits) return null;
		if (has_plus && digits.length >= 8) return digits;
		if (digits.length === 10) return `${INDIA_COUNTRY_CODE}${digits}`;
		if (digits.length >= 8 && digits.length <= 15) return digits;

		return null;
	};

	const get_whatsapp_link = (raw_phone) => {
		const normalized_phone = sanitize_phone(raw_phone);
		return normalized_phone ? `https://wa.me/${normalized_phone}` : null;
	};

	const get_call_link = (raw_phone) => {
		const normalized_phone = sanitize_phone(raw_phone);
		return normalized_phone ? `tel:+${normalized_phone}` : null;
	};

	frappe.ui.form.on("Participation", {
		refresh(frm) {
			const whatsapp_link = get_whatsapp_link(frm.doc.temp_phone);
			const call_link = get_call_link(frm.doc.temp_phone);
			const should_prompt_rating = frm.doc.logging_status === "Logged" && !frm.doc.rm_rating;

			if (whatsapp_link) {
				frm.add_custom_button(
					`${frappe.utils.icon("es-line-chat-alt", "sm")} ${__("WhatsApp")}`,
					() => {
						window.open(whatsapp_link, "_blank", "noopener,noreferrer");
					}
				);
			}

			if (call_link) {
				frm.add_custom_button(
					`${frappe.utils.icon("call", "sm")} ${__("Call")}`,
					() => {
						window.location.href = call_link;
					}
				);
			}

			if (should_prompt_rating) {
				frm.set_intro(
					__(
						"Logging is marked as Logged. Please submit Relationship Manager rating and comments."
					),
					"orange"
				);
			} else {
				frm.set_intro("");
			}
		},

		logging_status(frm) {
			if (frm.doc.logging_status === "Logged" && !frm.doc.rm_rating) {
				frappe.show_alert({
					message: __(
						"Please enter Relationship Manager rating now that logging is complete."
					),
					indicator: "orange",
				});
			}
		},
	});
})();