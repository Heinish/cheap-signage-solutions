#!/bin/bash
#
# CSS Signage Agent - FullPageOS Installation Script
# Adds CSS management API on top of existing FullPageOS installation
#

set -e  # Exit on error

echo "======================================"
echo "CSS Signage - FullPageOS Setup"
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

echo "Step 1: Installing system packages..."
apt-get update
apt-get install -y python3-pip jq git grim scrot

echo ""
echo "Step 2: Installing Python packages..."
pip3 install --break-system-packages flask psutil

echo ""
echo "Step 3: Creating directories..."
mkdir -p /opt/css-agent
mkdir -p /etc/css

echo ""
echo "Step 4: Installing CSS agent from GitHub..."
# Remove existing directory if it exists
rm -rf /opt/css
# Clone entire repo to /opt/css (keep as git repo for updates)
git clone https://github.com/Heinish/css.git /opt/css
# Create symlink for backwards compatibility
ln -sf /opt/css/pi-agent /opt/css-agent
chmod +x /opt/css/pi-agent/scripts/*.sh

echo ""
echo "Step 5: Creating default configuration..."
if [ ! -f /etc/css/config.json ]; then
    cat > /etc/css/config.json <<EOF
{
  "name": "Pi-$(hostname)",
  "room": "",
  "display_url": "http://localhost:5000/waiting",
  "api_port": 5000
}
EOF
    echo "Created default config at /etc/css/config.json"
else
    echo "Config file already exists, skipping..."
fi

echo ""
echo "Step 6: Installing CSS API service..."
# Only install the API service, not the kiosk (FullPageOS handles that)
# Run as root to allow writing to /boot/firmware and /etc/css
sed "s|User=pi|# User removed - running as root|g; s|/home/pi|$ACTUAL_HOME|g" \
    /opt/css-agent/systemd/css-agent.service > /etc/systemd/system/css-agent.service
systemctl daemon-reload

# Set proper permissions on config files
chmod 666 /etc/css/config.json
chmod 666 /boot/firmware/fullpageos.txt

echo ""
echo "Step 7: Disabling Chromium translate popup..."
# Create Chromium config directory
mkdir -p /home/$ACTUAL_USER/.config/chromium/Default
chown -R $ACTUAL_USER:$ACTUAL_USER /home/$ACTUAL_USER/.config/chromium

# Disable translate in Chromium preferences
cat > /home/$ACTUAL_USER/.config/chromium/Default/Preferences <<'PREFS_EOF'
{
   "translate": {
      "enabled": false
   },
   "translate_site_blacklist": ["*"]
}
PREFS_EOF
chown $ACTUAL_USER:$ACTUAL_USER /home/$ACTUAL_USER/.config/chromium/Default/Preferences

echo ""
echo "Step 8: Enabling CSS API service and auto-update timer..."
systemctl enable css-agent.service
systemctl start css-agent.service
systemctl enable css-auto-update.timer
systemctl start css-auto-update.timer

echo ""
echo "Step 9: Configuring log rotation to prevent SD card filling..."
/opt/css-agent/scripts/setup-log-rotation.sh

echo ""
echo "Step 10: Configuring FullPageOS to use CSS..."
# Update FullPageOS config to point to our API
if [ -f /boot/firmware/fullpageos.txt ]; then
    # Backup original
    cp /boot/firmware/fullpageos.txt /boot/firmware/fullpageos.txt.backup

    # Update URL to point to localhost (file contains just the URL, no key-value format)
    echo "http://localhost:5000/waiting" > /boot/firmware/fullpageos.txt
    echo "Updated FullPageOS configuration"
else
    echo "Warning: /boot/firmware/fullpageos.txt not found - you may need to configure FullPageOS manually"
fi

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "CSS API is now running on port 5000"
echo "FullPageOS will display content from http://localhost:5000/waiting"
echo ""
echo "Configuration file: /etc/css/config.json"
echo ""
echo "To restart the browser with new settings:"
echo "  sudo pkill chromium"
echo "  (or reboot: sudo reboot)"
echo ""
echo "To check API status:"
echo "  sudo systemctl status css-agent"
echo ""
echo "Next steps:"
echo "1. Add this Pi to your CSS Dashboard"
echo "2. Configure display URL via dashboard"
echo ""
read -p "Would you like to restart Chromium now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pkill chromium
fi
