#!/bin/bash
# Runs once on first boot. Reads /boot/firmware/css-config.txt (a plain
# "mainserver_url=http://..." line the user drops onto the boot partition
# after flashing - the same low-friction pattern Raspberry Pi Imager uses
# for its own OS customization) and seeds /etc/css/config.json with it.
# If the file isn't there, the agent just starts unconfigured and waits -
# mainserver_url can be set later over SSH.
set -e

CONFIG_TXT="/boot/firmware/css-config.txt"
CSS_CONFIG="/etc/css/config.json"
mkdir -p /etc/css

MAINSERVER_URL=""
if [ -f "$CONFIG_TXT" ]; then
    MAINSERVER_URL=$(grep -m1 '^mainserver_url=' "$CONFIG_TXT" 2>/dev/null | cut -d= -f2- | tr -d '\r\n' || true)
fi

python3 - "$MAINSERVER_URL" "$CSS_CONFIG" <<'PYEOF'
import json
import os
import sys

mainserver_url = sys.argv[1].strip() or None
path = sys.argv[2]

default = {
    "name": f"Pi-{os.uname().nodename}",
    "display_url": "http://localhost:5000/waiting",
    "api_port": 5000,
    "mainserver_url": None,
    "device_uid": None,
    "device_token": None,
}

if os.path.exists(path):
    with open(path) as f:
        cfg = json.load(f)
else:
    cfg = default

if mainserver_url and not cfg.get("mainserver_url"):
    cfg["mainserver_url"] = mainserver_url

with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
PYEOF

chmod 666 "$CSS_CONFIG"
