(function () {
	const INDIA_COUNTRY_CODE = "91";
	const RATING_FIELDS = new Set(["rm_rating", "rm_comment"]);
	const GRID_EDITABLE_FIELDS = new Set([
		"status",
		"kits_requested",
		"kits_delivered",
		"shipping_status",
		"logging_status",
		"hours_logged",
		"temp_full_name",
		"temp_phone",
		"temp_email",
		"temp_employee_id",
		"temp_company",
		"temp_address",
		"comments",
	]);
	const REPORT_ADD_FIELDS = [
		"modified",
		"volunteer",
		"temp_full_name",
		"status",
		"kits_requested",
		"kits_delivered",
		"shipping_status",
		"logging_status",
		"hours_logged",
	];

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

	const can_edit_rating_fields = (doc) => {
		const roles = frappe.user_roles || [];
		if (roles.includes("System Manager") || roles.includes("NGO Admin")) {
			return true;
		}
		return Boolean(doc._relationship_manager === frappe.session.user);
	};

	const save_participation_field = ({ doctype, docname, fieldname, value, modified }) =>
		new Promise((resolve, reject) => {
			frappe.call({
				method:
					"volunteering.volunteering.doctype.participation.participation.update_participation_field",
				args: {
					name: docname,
					fieldname,
					value,
					modified,
				},
				callback: (response) => resolve(response.message),
				error: (response) => reject(response || {}),
			});
		});

	const setup_report_view_editing = (listview) => {
		if (listview.view !== "Report" || listview._participation_report_setup) {
			return;
		}
		if (typeof listview.is_editable !== "function" || typeof listview.set_control_value !== "function") {
			return;
		}
		listview._participation_report_setup = true;

		const row_save_queues = new Map();
		const relationship_manager_cache = new Map();

		const load_relationship_managers = (docs) => {
			const volunteer_names = [
				...new Set(
					docs.map((doc) => doc.volunteer).filter((name) => name && !relationship_manager_cache.has(name))
				),
			];
			if (!volunteer_names.length) {
				return Promise.resolve();
			}

			return frappe.db
				.get_list("Volunteer", {
					filters: { name: ["in", volunteer_names] },
					fields: ["name", "relationship_manager"],
					limit: volunteer_names.length,
				})
				.then((rows) => {
					rows.forEach((row) => {
						relationship_manager_cache.set(row.name, row.relationship_manager);
					});
				});
		};

		const enrich_row = (doc) => {
			if (doc.volunteer) {
				doc._relationship_manager = relationship_manager_cache.get(doc.volunteer);
			}
			return doc;
		};

		const original_refresh = listview.refresh.bind(listview);
		listview.refresh = function (...args) {
			const refresh_result = original_refresh(...args);
			if (!refresh_result?.then) {
				return refresh_result;
			}

			return refresh_result.then(() => {
				if (!this.data?.length) return;
				return load_relationship_managers(this.data).then(() => {
					this.data.forEach(enrich_row);
				});
			});
		};

		const original_is_editable = listview.is_editable.bind(listview);
		listview.is_editable = function (df, data) {
			if (!df || !GRID_EDITABLE_FIELDS.has(df.fieldname)) {
				return false;
			}
			if (!original_is_editable(df, data)) {
				return false;
			}
			if (RATING_FIELDS.has(df.fieldname) && !can_edit_rating_fields(data)) {
				return false;
			}
			return true;
		};

		listview.set_control_value = function (doctype, docname, fieldname, value) {
			const row = this.data.find((doc) => doc.name === docname);
			const modified = row?.modified;
			const listview_ref = this;

			const save_field = () =>
				save_participation_field({
					doctype,
					docname,
					fieldname,
					value,
					modified,
				})
					.then((updated_doc) => {
						if (row) {
							Object.assign(row, updated_doc);
							enrich_row(row);
						}
						return updated_doc;
					})
					.catch((error) => {
						if (error?.exc_type === "TimestampMismatchError") {
							frappe.show_alert({
								message: __("This row was updated by someone else. Refreshing latest values."),
								indicator: "orange",
							});
							return frappe.db.get_doc(doctype, docname).then((doc) => {
								listview_ref.update_row(doc, false);
								return Promise.reject(error);
							});
						}
						return Promise.reject(error);
					});

			const previous = row_save_queues.get(docname) || Promise.resolve();
			const current = previous
				.catch(() => {})
				.then(() => save_field());
			row_save_queues.set(docname, current);
			return current;
		};
	};

	frappe.listview_settings["Participation"] = {
		add_fields: ["temp_phone", ...REPORT_ADD_FIELDS],
		onload(listview) {
			setup_report_view_editing(listview);
		},
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
