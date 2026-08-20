# CSS Signage Image

Builds a Raspberry Pi OS-based `.img` with the CSS agent and our own
minimal kiosk stack baked in from first boot. No FullPageOS anywhere -
X11 + openbox + Chromium, launched by a systemd unit we own
(`css-kiosk.service`), controlled the same way the agent already controls
everything else.

## What's in the image

- Raspberry Pi OS Lite (Bookworm, arm64) as the base
- `xserver-xorg` + `openbox` + `chromium`, kiosk-launched via `startx` from
  `css-kiosk.service` (runs as a dedicated `kiosk` user)
- The CSS agent (`/opt/css`, same repo, same `git pull`-based update flow as
  the FullPageOS install)
- `css-firstboot.service` - reads `mainserver_url=...` from
  `/boot/firmware/css-config.txt` on first boot, if you dropped one there
- HDMI forced to 1920x1080@60, translate popup disabled, disk cache capped -
  same defaults as the FullPageOS install script

Existing FullPageOS-based Pis are unaffected and keep working - this is a
separate image, not a migration of existing hardware. `pi-agent/device_control.py`
detects which kiosk backend it's running on
(`/boot/firmware/fullpageos.txt` present or not) and uses the right one, so
the exact same agent code runs on both.

## Building

Requires Docker (pi-gen's `build-docker.sh` does the whole build inside a
privileged container - no need to hand-install debootstrap/qemu yourself).

```bash
cd image-builder
./build.sh          # builds against pi-gen's `bookworm` branch
```

Output lands in `image-builder/output/*.img.xz`. A full build bootstraps a
Debian base system, installs packages under qemu emulation, and assembles
the image - expect 45-90+ minutes and ~10GB of scratch space.

**This has not been build-tested yet** (no Docker/Linux environment was
available in the session that wrote it) - treat the first real run as a
debug pass, most likely around pi-gen's exact stage-script conventions.

### Building via GitHub Actions instead

`.github/workflows/build-pi-image.yml` runs the same `build.sh` on a hosted
Linux runner (which has Docker already) and uploads the resulting image as
a build artifact. Trigger it manually from the Actions tab, or push a tag
matching `image-v*` to also attach the image to a GitHub release.

## Flashing

1. Flash `css-signage-<version>.img.xz` with Raspberry Pi Imager
2. Use Imager's own OS customization (gear icon) for hostname/WiFi/SSH -
   that part is untouched, standard Raspberry Pi OS
3. Optionally drop a `css-config.txt` file onto the boot partition after
   flashing, containing:
   ```
   mainserver_url=http://your-mainserver:8000
   ```
   so the Pi pairs itself against your mainserver on first boot instead of
   sitting unconfigured until you set it over SSH
4. Boot it - it'll show a pairing code on screen once the agent is up
