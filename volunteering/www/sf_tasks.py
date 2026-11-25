"""Public shell only; session and App chat access are checked by authenticated APIs."""
from pathlib import Path
import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    path = Path(frappe.get_app_path("volunteering", "public", "sf_tasks", "index.html"))
    context.pwa_html = path.read_text() if path.is_file() else "<h1>SF Tasks PWA</h1><p>The PWA build is not installed yet.</p>"
