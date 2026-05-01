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

	frappe.listview_settings["Participation"] = {
		add_fields: ["temp_phone"],
		formatters: {
			temp_phone(value, _df, doc) {
				const phone_value = frappe.utils.escape_html(value || "");
				const whatsapp_link = get_whatsapp_link(doc.temp_phone);
				const call_link = get_call_link(doc.temp_phone);

				if (!whatsapp_link && !call_link) return phone_value;

				const whatsapp_action = whatsapp_link
					? `<a href="${whatsapp_link}" target="_blank" rel="noopener noreferrer" class="small text-primary mr-2" onclick="event.stopPropagation();">${__("WhatsApp")}</a>`
					: "";
				const call_action = call_link
					? `<a href="${call_link}" class="small text-primary" onclick="event.stopPropagation();">${__("Call")}</a>`
					: "";

				return `
					<span>${phone_value}</span>
					<span class="visible-xs">${whatsapp_action}${call_action}</span>
				`;
			},
		},
		dropdown_button: {
			get_label: __("Actions"),
			buttons: [
				{
					get_label: `${frappe.utils.icon("es-line-chat-alt", "sm")} ${__("WhatsApp")}`,
					get_description: () => __("Open WhatsApp chat"),
					show: (doc) => Boolean(get_whatsapp_link(doc.temp_phone)),
					action: (doc) => {
						const whatsapp_link = get_whatsapp_link(doc.temp_phone);
						if (!whatsapp_link) return;
						window.open(whatsapp_link, "_blank", "noopener,noreferrer");
					},
				},
				{
					get_label: `${frappe.utils.icon("call", "sm")} ${__("Call")}`,
					get_description: () => __("Open phone dialer"),
					show: (doc) => Boolean(get_call_link(doc.temp_phone)),
					action: (doc) => {
						const call_link = get_call_link(doc.temp_phone);
						if (!call_link) return;
						window.location.href = call_link;
					},
				},
			],
		},
	};
})();
