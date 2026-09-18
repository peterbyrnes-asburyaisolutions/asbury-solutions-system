#!/usr/bin/env python3
"""Prepare a Genesis Mini SD card image from sdcard/AOS.

Copies the tree to a destination (mounted card or staging dir) and optionally
injects Wi-Fi / LLM / sync credentials from environment variables or CLI flags.

Env (optional):
  AOS_WIFI_SSID, AOS_WIFI_PASS
  AOS_LLM_ENABLED, AOS_LLM_BASE_URL, AOS_LLM_API_KEY, AOS_LLM_MODEL
  AOS_SYNC_ENABLED, AOS_SYNC_BASE_URL, AOS_SYNC_API_KEY, AOS_SYNC_DEVICE_ID
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "sdcard" / "AOS"

# EverOS PathSafeId charset (app_id / project_id / sender_id / device_id).
DEVICE_ID_RE = re.compile(r"^[a-zA-Z0-9_.@+-]+$")


def validate_device_id(device_id: str) -> None:
    if not device_id:
        return
    if device_id in (".", "..") or not DEVICE_ID_RE.match(device_id):
        raise SystemExit(
            f"error: invalid sync.device_id {device_id!r} "
            f"(must match ^[a-zA-Z0-9_.@+-]+$ and not be '.' / '..')"
        )
    if len(device_id) > 128:
        raise SystemExit("error: sync.device_id exceeds 128 characters")


def inject_manifest(manifest_path: Path, args: argparse.Namespace) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    wifi = data.setdefault("wifi", {})
    llm = data.setdefault("llm", {})
    sync = data.setdefault("sync", {})

    ssid = args.wifi_ssid or os.environ.get("AOS_WIFI_SSID", "")
    password = args.wifi_pass or os.environ.get("AOS_WIFI_PASS", "")
    if ssid:
        wifi["ssid"] = ssid
    if password or args.wifi_pass is not None or "AOS_WIFI_PASS" in os.environ:
        wifi["pass"] = password

    if args.llm_enabled is not None:
        llm["enabled"] = args.llm_enabled
    elif "AOS_LLM_ENABLED" in os.environ:
        llm["enabled"] = os.environ["AOS_LLM_ENABLED"].lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    base_url = args.llm_base_url or os.environ.get("AOS_LLM_BASE_URL")
    api_key = args.llm_api_key or os.environ.get("AOS_LLM_API_KEY")
    model = args.llm_model or os.environ.get("AOS_LLM_MODEL")
    if base_url:
        llm["base_url"] = base_url
    if api_key:
        llm["api_key"] = api_key
    if model:
        llm["model"] = model

    if args.sync_enabled is not None:
        sync["enabled"] = args.sync_enabled
    elif "AOS_SYNC_ENABLED" in os.environ:
        sync["enabled"] = os.environ["AOS_SYNC_ENABLED"].lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    sync_base = args.sync_base_url or os.environ.get("AOS_SYNC_BASE_URL")
    sync_key = args.sync_api_key or os.environ.get("AOS_SYNC_API_KEY")
    sync_device = args.sync_device_id or os.environ.get("AOS_SYNC_DEVICE_ID")
    if sync_base:
        sync["base_url"] = sync_base
    if sync_key:
        sync["api_key"] = sync_key
    if sync_device:
        sync["device_id"] = sync_device
    if args.sync_interval_s is not None:
        sync["interval_s"] = args.sync_interval_s

    validate_device_id(str(sync.get("device_id", "")))

    manifest_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dest",
        type=Path,
        help="Destination directory (e.g. /Volumes/GENESIS or ./out/AOS)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help=f"Source AOS tree (default: {DEFAULT_SRC})",
    )
    parser.add_argument("--wifi-ssid", default=None)
    parser.add_argument("--wifi-pass", default=None)
    parser.add_argument(
        "--llm-enabled",
        type=lambda s: s.lower() in ("1", "true", "yes", "on"),
        default=None,
    )
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-api-key", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--sync-enabled",
        type=lambda s: s.lower() in ("1", "true", "yes", "on"),
        default=None,
    )
    parser.add_argument("--sync-base-url", default=None)
    parser.add_argument("--sync-api-key", default=None)
    parser.add_argument("--sync-device-id", default=None)
    parser.add_argument("--sync-interval-s", type=int, default=None)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove destination AOS tree before copy",
    )
    args = parser.parse_args()

    src: Path = args.src
    dest: Path = args.dest

    if not src.is_dir():
        print(f"error: source not found: {src}", file=sys.stderr)
        return 1

    # Allow dest to be the card root or the AOS folder itself.
    if dest.name.upper() == "AOS":
        aos_dest = dest
    else:
        aos_dest = dest / "AOS"

    if args.clean and aos_dest.exists():
        shutil.rmtree(aos_dest)

    aos_dest.parent.mkdir(parents=True, exist_ok=True)
    if aos_dest.exists():
        # Merge-copy: replace files, keep extra user data (e.g. memory.jsonl)
        for path in src.rglob("*"):
            rel = path.relative_to(src)
            target = aos_dest / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    else:
        shutil.copytree(src, aos_dest)

    inject_manifest(aos_dest / "AGENT" / "manifest.json", args)
    print(f"prepared SD image at {aos_dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
