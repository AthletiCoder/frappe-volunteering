#!/usr/bin/env python3
"""Verify and prepare signed, versioned APKs and the two independent update feeds.

This command does not upload, push or deploy anything. See README for publication.
Only certificate fingerprints are public; private signing material stays out of Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

REPO = "AthletiCoder/frappe-volunteering"
MAX_APK_BYTES = 100 * 1024 * 1024


def manifest(metadata, certificate, expected_certificate, content, package, notes):
    if metadata["package"] != package:
        raise ValueError("APK package does not match its update channel")
    if certificate != expected_certificate:
        raise ValueError("APK signing key differs from the existing app")
    if package == "org.sevamrita.mobile" and metadata["debuggable"]:
        raise ValueError("Production APK must not be debuggable")
    name = metadata["version_name"]
    local = package.endswith(".local")
    if not re.fullmatch(r"\d+\.\d+\.\d+" + ("-local" if local else ""), name):
        raise ValueError("Unexpected version name for this channel")
    if metadata["version_code"] <= 0 or metadata["min_sdk"] < 26 or not 0 < len(content) <= MAX_APK_BYTES:
        raise ValueError("Invalid APK version, SDK or size")
    version = name.removesuffix("-local")
    filename = f"{'SF-testing' if local else 'SF-Tasks'}-{version}.apk"
    return {
        "package_name": package, "version_code": metadata["version_code"], "version_name": name,
        "min_sdk": metadata["min_sdk"], "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "apk_url": f"https://github.com/{REPO}/releases/download/sf-tasks-v{version}/{filename}",
        "release_notes": notes.strip()[:4000],
    }


def inspect(apk, build_tools):
    verified = subprocess.check_output([str(build_tools / "apksigner"), "verify", "--print-certs", str(apk)], text=True)
    certificates = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([a-f0-9]{64})", verified)
    if len(certificates) != 1:
        raise ValueError("Expected exactly one APK signer")
    badging = subprocess.check_output([str(build_tools / "aapt"), "dump", "badging", str(apk)], text=True)
    found = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging)
    sdk = re.search(r"sdkVersion:'(\d+)'", badging)
    if not found or not sdk:
        raise ValueError("Cannot read APK metadata")
    return {"package": found[1], "version_code": int(found[2]), "version_name": found[3],
            "min_sdk": int(sdk[1]), "debuggable": "application-debuggable" in badging}, certificates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--testing", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    sdk = Path(os.environ.get("ANDROID_HOME", Path.home() / "Library/Android/sdk"))
    parser.add_argument("--build-tools", type=Path, default=sdk / "build-tools/35.0.0")
    args = parser.parse_args()
    pins = json.loads(Path(__file__).with_name("release-certificates.json").read_text())
    prepared = []
    for package, apk, feed in (("org.sevamrita.mobile", args.tasks, "sf-tasks-update.json"),
                               ("org.sevamrita.mobile.local", args.testing, "sf-testing-update.json")):
        metadata, certificate = inspect(apk, args.build_tools)
        data = manifest(metadata, certificate, pins[package], apk.read_bytes(), package, args.notes.read_text())
        prepared.append((apk, feed, data))
    if prepared[0][2]["version_code"] != prepared[1][2]["version_code"] or prepared[0][2]["version_name"] != prepared[1][2]["version_name"].removesuffix("-local"):
        raise ValueError("Production and testing release versions must match")
    args.output.mkdir(parents=True, exist_ok=True)
    for apk, feed, data in prepared:
        dest = args.output / data["apk_url"].rsplit("/", 1)[1]
        if apk.resolve() != dest.resolve():
            shutil.copyfile(apk, dest)
        (args.output / feed).write_text(json.dumps(data, indent=2) + "\n")
        (args.output / (dest.name + ".sha256")).write_text(f"{data['sha256']}  {dest.name}\n")
    print(f"Verified release {prepared[0][2]['version_name']} prepared in {args.output}")


if __name__ == "__main__":
    main()
