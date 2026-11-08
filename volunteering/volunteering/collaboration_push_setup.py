"""CLI-only Firebase setup; private credentials must already be in site/private/."""
import json
from pathlib import Path
import re

import frappe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def firebase_config(service_account, android_files):
	project = service_account.get("project_id", "")
	if service_account.get("type") != "service_account" or not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project):
		raise ValueError("Choose a Firebase service-account JSON file.")
	key = serialization.load_pem_private_key(service_account.get("private_key", "").encode(), password=None)
	if not isinstance(key, rsa.RSAPrivateKey) or not service_account.get("client_email", "").endswith(".iam.gserviceaccount.com"):
		raise ValueError("Invalid Firebase service account.")
	apps = {}
	sender = None
	for package, data in android_files.items():
		info = data.get("project_info", {})
		if info.get("project_id") != project or not str(info.get("project_number", "")).isdigit():
			raise ValueError("All Firebase files must belong to the same project.")
		client = next((c for c in data.get("client", []) if c.get("client_info", {}).get("android_client_info", {}).get("package_name") == package), None)
		if not client or not client.get("api_key") or not client["api_key"][0].get("current_key"):
			raise ValueError(f"The Android config does not contain {package}.")
		app_id = client["client_info"].get("mobilesdk_app_id", "")
		if not app_id.startswith(f"1:{info['project_number']}:android:"):
			raise ValueError("Invalid Firebase Android app ID.")
		sender = str(info["project_number"])
		apps[package] = {"app_id": app_id, "api_key": client["api_key"][0]["current_key"]}
	return {"enabled": True, "project_id": project, "sender_id": sender, "apps": apps, "service_account": service_account}


def configure(service_account_file, tasks_config_file, testing_config_file=None):
	if frappe.session.user != "Administrator":
		frappe.throw("Run this setup as Administrator through the bench CLI.", frappe.PermissionError)
	private = Path(frappe.get_site_path("private")).resolve()
	def load(filename):
		file = Path(filename).resolve()
		if not file.is_relative_to(private):
			frappe.throw("Place the Firebase setup files inside this site's private directory first.")
		return json.loads(file.read_text())
	files = {"org.sevamrita.mobile": load(tasks_config_file)}
	if testing_config_file:
		files["org.sevamrita.mobile.local"] = load(testing_config_file)
	config = firebase_config(load(service_account_file), files)
	from frappe.installer import update_site_config
	update_site_config("sf_tasks_firebase", config)
	frappe.conf.sf_tasks_firebase = config
	frappe.cache.delete_value("sf_tasks_fcm_access_token")
	return {"configured": True, "project_id": config["project_id"], "packages": list(config["apps"])}
