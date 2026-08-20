#!/bin/bash -e
# Installs the CSS agent + our own minimal kiosk stack. No FullPageOS
# anywhere in this image - the agent owns the kiosk process directly.

CSS_REPO_URL="${CSS_REPO_URL:-https://github.com/Heinish/css.git}"
CSS_REPO_REF="${CSS_REPO_REF:-main}"

# --- App code: clone the same repo the FullPageOS install script uses, so
# the existing /api/update (git pull) flow works identically on this image. ---
rm -rf "${ROOTFS_DIR}/opt/css"
git clone --branch "${CSS_REPO_REF}" --depth 1 "${CSS_REPO_URL}" "${ROOTFS_DIR}/opt/css"
ln -sf /opt/css/pi-agent "${ROOTFS_DIR}/opt/css-agent"

# --- Our own kiosk launcher + first-boot provisioning script ---
install -d -m 755 "${ROOTFS_DIR}/opt/css/pi-agent/kiosk"
install -m 755 files/start-kiosk.sh "${ROOTFS_DIR}/opt/css/pi-agent/kiosk/start-kiosk.sh"
install -m 755 files/css-firstboot.sh "${ROOTFS_DIR}/opt/css/pi-agent/kiosk/css-firstboot.sh"

install -m 644 files/css-kiosk.service "${ROOTFS_DIR}/etc/systemd/system/css-kiosk.service"
install -m 644 files/css-firstboot.service "${ROOTFS_DIR}/etc/systemd/system/css-firstboot.service"

# --- Config directory + default config ---
install -d -m 755 "${ROOTFS_DIR}/etc/css"
cat > "${ROOTFS_DIR}/etc/css/config.json" <<'EOF'
{
  "name": "CSS Display",
  "display_url": "http://localhost:5000/waiting",
  "api_port": 5000,
  "mainserver_url": null,
  "device_uid": null,
  "device_token": null
}
EOF
chmod 666 "${ROOTFS_DIR}/etc/css/config.json"

on_chroot << 'EOF'
# Dedicated, unprivileged kiosk user - the agent (running as root, see
# css-agent.service) drops privileges to this user for xrandr/scrot via
# `sudo -u kiosk`, same as it does on a FullPageOS install.
if ! id kiosk >/dev/null 2>&1; then
    useradd -m -G video,input,render,tty kiosk
fi

# pip packages not available/prebuilt via apt
pip3 install --break-system-packages websockets

# systemd units shipped in the repo itself (same ones the FullPageOS
# install script uses) - templated the same way: run as root.
sed "s|{USER}|root|g" /opt/css/pi-agent/systemd/css-agent.service > /etc/systemd/system/css-agent.service
cp /opt/css/pi-agent/systemd/css-auto-update.timer /etc/systemd/system/
cp /opt/css/pi-agent/systemd/css-auto-update.service /etc/systemd/system/
cp /opt/css/pi-agent/systemd/css-daily-reboot.timer /etc/systemd/system/
cp /opt/css/pi-agent/systemd/css-daily-reboot.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable css-firstboot.service
systemctl enable css-agent.service
systemctl enable css-kiosk.service

# Deliberately NOT forcing hdmi_group/hdmi_mode/framebuffer_width/height
# here. Those are legacy (non-KMS) firmware-framebuffer settings carried
# over from the old FullPageOS install script - this image uses the
# default KMS graphics driver (dtoverlay=vc4-kms-v3d), and mixing legacy
# framebuffer forcing with KMS crashes Xorg on startup (signal 6, right
# after loading the "fb" submodule). Resolution is instead requested at
# the Xorg level via /usr/share/X11/xorg.conf.d/10-resolution.conf,
# written by the agent itself (device_control.ensure_display_resolution),
# which is the KMS-compatible way to do it.
EOF
