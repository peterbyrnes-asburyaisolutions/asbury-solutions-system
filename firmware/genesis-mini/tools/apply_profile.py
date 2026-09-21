#!/usr/bin/env python3
"""Swap the profile assigned to an AX22 module port on a Genesis Mini SD image.

Example:
  python tools/apply_profile.py ./sdcard/AOS 4 control
  python tools/apply_profile.py /Volumes/GENESIS/AOS 3 climate --label "Lab DHT"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VALID_PORTS = (2, 3, 4)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "aos_root",
        type=Path,
        help="Path to AOS directory (contains MODULES/)",
    )
    parser.add_argument("port", type=int, choices=VALID_PORTS)
    parser.add_argument(
        "profile",
        help="Profile name under MODULES/profiles/ (panel, climate, ambient, control)",
    )
    parser.add_argument("--label", default=None, help="Optional human label")
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Mark the port enabled=false",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Mark the port enabled=true",
    )
    args = parser.parse_args()

    aos: Path = args.aos_root
    if aos.name.upper() != "AOS" and (aos / "AOS").is_dir():
        aos = aos / "AOS"

    modules = aos / "MODULES"
    profile_path = modules / "profiles" / f"{args.profile}.json"
    port_path = modules / f"port{args.port}.json"

    if not profile_path.is_file():
        print(f"error: profile not found: {profile_path}", file=sys.stderr)
        return 1

    profile = load_json(profile_path)
    kind = profile.get("kind", args.profile)

    if port_path.is_file():
        port_cfg = load_json(port_path)
    else:
        port_cfg = {"port": args.port}

    port_cfg["port"] = args.port
    port_cfg["profile"] = args.profile
    port_cfg["kind"] = kind
    if args.label is not None:
        port_cfg["label"] = args.label
    elif "label" not in port_cfg:
        port_cfg["label"] = args.profile

    if args.disable:
        port_cfg["enabled"] = False
    elif args.enable:
        port_cfg["enabled"] = True
    else:
        port_cfg.setdefault("enabled", True)

    port_path.write_text(json.dumps(port_cfg, indent=2) + "\n", encoding="utf-8")
    print(f"port {args.port} -> profile={args.profile} kind={kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
