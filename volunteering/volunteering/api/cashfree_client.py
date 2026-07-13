"""Cashfree HTTP client for volunteering donations."""

from __future__ import annotations

import json
from typing import Any

import frappe
import requests

from volunteering.volunteering.doctype.cashfree_settings.cashfree_settings import (
	get_cashfree_settings,
)

API_VERSION = "2023-08-01"
SANDBOX_BASE = "https://sandbox.cashfree.com/pg"
PRODUCTION_BASE = "https://api.cashfree.com/pg"


def _base_url(environment: str) -> str:
	if (environment or "").lower() == "production":
		return PRODUCTION_BASE
	return SANDBOX_BASE


def _headers(settings) -> dict[str, str]:
	return {
		"Content-Type": "application/json",
		"x-api-version": API_VERSION,
		"x-client-id": settings.app_id,
		"x-client-secret": settings.get_password("secret_key"),
	}


def create_order(
	*,
	order_id: str,
	amount: float,
	customer_id: str,
	customer_phone: str,
	customer_email: str,
	customer_name: str,
	return_url: str | None = None,
) -> dict[str, Any]:
	settings = get_cashfree_settings()
	payload: dict[str, Any] = {
		"order_id": order_id,
		"order_amount": float(amount),
		"order_currency": "INR",
		"customer_details": {
			"customer_id": customer_id[:50],
			"customer_phone": _digits_phone(customer_phone),
			"customer_email": customer_email,
			"customer_name": customer_name,
		},
		"order_meta": {},
	}
	if return_url:
		payload["order_meta"]["return_url"] = return_url

	url = f"{_base_url(settings.environment)}/orders"
	response = requests.post(
		url,
		headers={**_headers(settings), "x-idempotency-key": order_id},
		data=json.dumps(payload),
		timeout=30,
	)
	try:
		data = response.json()
	except ValueError:
		frappe.throw(f"Cashfree create order failed: HTTP {response.status_code}")

	if response.status_code >= 400:
		message = data.get("message") or data.get("error") or str(data)
		frappe.throw(f"Cashfree create order failed: {message}")

	return data


def get_order(order_id: str) -> dict[str, Any]:
	settings = get_cashfree_settings()
	url = f"{_base_url(settings.environment)}/orders/{order_id}"
	response = requests.get(url, headers=_headers(settings), timeout=30)
	try:
		data = response.json()
	except ValueError:
		frappe.throw(f"Cashfree get order failed: HTTP {response.status_code}")

	if response.status_code >= 400:
		message = data.get("message") or data.get("error") or str(data)
		frappe.throw(f"Cashfree get order failed: {message}")

	return data


def _digits_phone(raw: str) -> str:
	digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
	if len(digits) >= 10:
		return digits[-10:]
	return digits or "9999999999"
