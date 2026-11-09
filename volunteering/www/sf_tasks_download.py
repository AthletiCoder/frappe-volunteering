import json
import re
from pathlib import Path

import frappe

no_cache = 1
sitemap = 0

CHANNELS = (
    ("sf-tasks", "SF Tasks", "org.sevamrita.mobile"),
    ("sf-testing", "SF testing", "org.sevamrita.mobile.local"),
)


def get_context(context):
    context.title = "SF Tasks downloads"
    release_dir = Path(frappe.get_app_path("volunteering", "public", "android_updates"))
    context.channels = [
        {"id": channel, "label": label, "release": _release(release_dir, channel, label, package)}
        for channel, label, package in CHANNELS
    ]


def _release(release_dir, channel, label, package):
    try:
        metadata = json.loads((release_dir / f"{channel}-update.json").read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or metadata.get("package_name") != package:
            return None
        version = metadata.get("version_name")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-local)?", version):
            return None
        filename = f"{label.replace(' ', '-')}-{version.removesuffix('-local')}.apk"
        download_path = f"/assets/volunteering/android_updates/{filename}"
        digest = metadata.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            return None
        apk = release_dir / filename
        if not apk.is_file():
            return None
        size = apk.stat().st_size
        if size != metadata.get("size_bytes"):
            return None
    except (OSError, ValueError):
        return None
    return {
        "version": version,
        "size_mb": f"{size / (1024 * 1024):.1f}",
        "url": download_path,
        "sha256": digest,
        "notes": str(metadata.get("release_notes", ""))[:4000],
    }
