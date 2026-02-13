#!/bin/bash
#
# CSS Signage Agent - Installation Script
# For Raspberry Pi OS (Debian-based)
#

set -e  # Exit on error

echo "======================================"
echo "CSS Signage Agent - Installation"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)
echo "Detected user: $ACTUAL_USER"
echo "Home directory: $ACTUAL_HOME"
echo ""

# Check if running on a Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Step 1: Updating system packages..."
apt-get update
apt-get upgrade -y

echo ""
echo "Step 2: Installing dependencies..."
apt-get install -y \
    chromium \
    python3 \
    python3-pip \
    python3-venv \
    git \
    jq \
    xdotool \
    unclutter \
    x11-xserver-utils \
    grim \
    scrot

echo ""
echo "Step 3: Installing Python packages..."
pip3 install --break-system-packages flask psutil

echo ""
echo "Step 4: Creating directories..."
mkdir -p /opt/css-agent
mkdir -p /etc/css

echo ""
echo "Step 5: Copying CSS agent files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp -r "$SCRIPT_DIR"/* /opt/css-agent/
chmod +x /opt/css-agent/scripts/*.sh

echo ""
echo "Step 6: Creating default configuration..."
if [ ! -f /etc/css/config.json ]; then
    cat > /etc/css/config.json <<EOF
{
  "name": "Pi-$(hostname)",
  "room": "",
  "display_url": "file:///opt/css-agent/static/waiting.html",
  "api_port": 5000
}
EOF
    echo "Created default config at /etc/css/config.json"
else
    echo "Config file already exists, skipping..."
fi

echo ""
echo "Step 7: Installing systemd services..."
# Copy service files and replace 'pi' user with actual user
for service_file in /opt/css-agent/systemd/*.service; do
    filename=$(basename "$service_file")
    sed "s|User=pi|User=$ACTUAL_USER|g; s|/home/pi|$ACTUAL_HOME|g" "$service_file" > "/etc/systemd/system/$filename"
done
cp /opt/css-agent/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload

echo ""
echo "Step 8: Enabling services..."
systemctl enable css-agent.service
# css-kiosk.service is NOT enabled by default - enable it manually after testing
# systemctl enable css-kiosk.service
systemctl enable css-daily-reboot.timer

echo ""
echo "Step 9: Configuring auto-login (for kiosk mode)..."
# Enable auto-login to desktop for user 'pi'
raspi-config nonint do_boot_behaviour B4

echo ""
echo "Step 10: Skipping desktop autostart (use systemd services instead)..."
# Note: Desktop autostart files are skipped to prevent boot loops
# The kiosk will be controlled via systemd services only

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Configuration file: /etc/css/config.json"
echo "Edit this file to customize your Pi's name and settings"
echo ""
echo "Next steps:"
echo "1. Reboot the Pi: sudo reboot"
echo "2. After reboot, the Pi will boot into kiosk mode"
echo "3. Add this Pi to your CSS Dashboard"
echo ""
echo "Services installed:"
echo "  - css-agent.service (REST API)"
echo "  - css-kiosk.service (Chromium browser)"
echo "  - css-daily-reboot.timer (Daily reboot at 3 AM)"
echo ""
echo "To start services now without rebooting:"
echo "  sudo systemctl start css-agent"
echo "  sudo systemctl start css-kiosk"
echo ""
read -p "Would you like to reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
fi
