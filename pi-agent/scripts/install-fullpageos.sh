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
apt-get install -y python3-pip jq git grim scrot fbgrab

echo ""
echo "Step 2: Installing Python packages..."
pip3 install --break-system-packages flask psutil Pillow websockets

echo ""
echo "Step 3: Creating directories..."
mkdir -p /etc/css

echo ""
echo "Step 4: Installing CSS agent from GitHub..."
# Move to a safe directory first - if we're inside /opt/css, removing it
# would destroy our working directory and cause git clone to fail
cd /tmp
# Remove existing directory/symlink if it exists
rm -rf /opt/css
rm -rf /opt/css-agent
# Clone entire repo to /opt/css (keep as git repo for updates)
git clone https://github.com/Heinish/css.git /opt/css
# Create symlink so /opt/css-agent points to /opt/css/pi-agent
ln -sf /opt/css/pi-agent /opt/css-agent
chmod +x /opt/css/pi-agent/scripts/*.sh

echo ""
echo "Step 5: Creating default configuration..."
if [ ! -f /etc/css/config.json ]; then
    cat > /etc/css/config.json <<EOF
{
  "name": "Pi-$(hostname)",
  "display_url": "http://localhost:5000/waiting",
  "api_port": 5000,
  "mainserver_url": ${CSS_MAINSERVER_URL:+\"$CSS_MAINSERVER_URL\"}${CSS_MAINSERVER_URL:-null},
  "device_uid": null,
  "device_token": null
}
EOF
    echo "Created default config at /etc/css/config.json"
    if [ -z "$CSS_MAINSERVER_URL" ]; then
        echo "  No mainserver_url set - the display will wait until you set one."
        echo "  Re-run with: CSS_MAINSERVER_URL=http://your-server:8000 curl -sSL ... | sudo -E bash"
        echo "  Or set it later: sudo nano /etc/css/config.json"
    else
        echo "  mainserver_url set to $CSS_MAINSERVER_URL"
    fi
else
    echo "Config file already exists, skipping..."
fi

echo ""
echo "Step 6: Installing CSS API service and timers..."
# Only install the API service, not the kiosk (FullPageOS handles that)
# Replace {USER} placeholder with actual user, but run as root for /boot/firmware access
sed "s|{USER}|root|g; s|/home/pi|$ACTUAL_HOME|g" \
    /opt/css-agent/systemd/css-agent.service > /etc/systemd/system/css-agent.service

# Install auto-update timer and service
cp /opt/css-agent/systemd/css-auto-update.timer /etc/systemd/system/
cp /opt/css-agent/systemd/css-auto-update.service /etc/systemd/system/

# Install daily reboot timer and service
cp /opt/css-agent/systemd/css-daily-reboot.timer /etc/systemd/system/
cp /opt/css-agent/systemd/css-daily-reboot.service /etc/systemd/system/

systemctl daemon-reload

# Set proper permissions on config files
chmod 666 /etc/css/config.json
chmod 666 /boot/firmware/fullpageos.txt

echo ""
echo "Step 7: Disabling Chromium translate popup..."
# Detect which user FullPageOS runs the X session / Chromium as
# This varies per Pi - we detect it dynamically, never hardcode
CHROMIUM_USER=""

# Method 1: Check who's running Chromium right now
if [ -z "$CHROMIUM_USER" ]; then
    CHROMIUM_USER=$(ps aux 2>/dev/null | grep '[c]hromium' | head -1 | awk '{print $1}')
fi

# Method 2: Check who's running the X server
if [ -z "$CHROMIUM_USER" ] || [ "$CHROMIUM_USER" = "root" ]; then
    CHROMIUM_USER=$(ps aux 2>/dev/null | grep '[X]org' | head -1 | awk '{print $1}')
fi

# Method 3: Check lightdm auto-login config (FullPageOS uses lightdm)
if [ -z "$CHROMIUM_USER" ] || [ "$CHROMIUM_USER" = "root" ]; then
    if [ -f /etc/lightdm/lightdm.conf ]; then
        CHROMIUM_USER=$(grep -oP 'autologin-user=\K.*' /etc/lightdm/lightdm.conf 2>/dev/null)
    fi
fi

# Method 4: Fallback to the user who ran the install
if [ -z "$CHROMIUM_USER" ] || [ "$CHROMIUM_USER" = "root" ]; then
    CHROMIUM_USER="$ACTUAL_USER"
fi

CHROMIUM_HOME="/home/$CHROMIUM_USER"
echo "  Chromium user detected: $CHROMIUM_USER"

# === FIX 1: /etc/chromium.d/ (the CORRECT Debian/Raspberry Pi OS way) ===
# On Debian-based systems, /usr/bin/chromium-browser is a wrapper script that
# sources all files in /etc/chromium.d/ and adds CHROMIUM_FLAGS to the command line.
# This is the ONLY reliable way to pass flags on Raspberry Pi OS.
# (chromium-flags.conf is an Arch Linux thing and does NOT work here)
mkdir -p /etc/chromium.d
cat > /etc/chromium.d/99-css-disable-translate <<'CHROMIUMD_EOF'
# CSS Signage: Disable Chromium translate popup
export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disable-features=Translate,TranslateUI --disable-translate"
CHROMIUMD_EOF
echo "  Created /etc/chromium.d/99-css-disable-translate"

cat > /etc/chromium.d/50-css-cache-limit <<'CHROMIUMD_EOF'
# CSS Signage: Limit disk cache to 50MB to prevent SD card filling
export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disk-cache-size=52428800 --media-cache-size=52428800"
CHROMIUMD_EOF
echo "  Created /etc/chromium.d/50-css-cache-limit"

# === FIX 2: Patch FullPageOS start_chromium_browser script ===
# FullPageOS has a flags array with --disable-features=TranslateUI (only UI, not the engine).
# If there are TWO --disable-features= flags, Chromium only uses the LAST one.
# So we MUST change TranslateUI to Translate,TranslateUI in the start script itself,
# and also add --disable-translate to the flags array.
PATCHED_LAUNCH=false

# Search all known locations for the FullPageOS chromium launch script
for launch_script in \
    "$CHROMIUM_HOME/scripts/start_chromium_browser" \
    /home/*/scripts/start_chromium_browser \
    /opt/custompios/scripts/start_chromium_browser \
    /opt/fullpageos/scripts/start_chromium_browser; do
    if [ -f "$launch_script" ]; then
        # Replace --disable-features=TranslateUI with the full Translate,TranslateUI
        if grep -q "disable-features=TranslateUI" "$launch_script" 2>/dev/null; then
            sed -i 's|--disable-features=TranslateUI|--disable-features=Translate,TranslateUI|g' "$launch_script"
            # Also add --disable-translate flag if not present
            if ! grep -q "\-\-disable-translate" "$launch_script" 2>/dev/null; then
                sed -i 's|--disable-features=Translate,TranslateUI|--disable-features=Translate,TranslateUI\n   --disable-translate|' "$launch_script"
            fi
            echo "  Patched: $launch_script"
            PATCHED_LAUNCH=true
        elif grep -q "disable-features=Translate,TranslateUI" "$launch_script" 2>/dev/null; then
            echo "  Already patched: $launch_script"
            PATCHED_LAUNCH=true
        fi
    fi
done

if [ "$PATCHED_LAUNCH" = false ]; then
    echo "  Warning: Could not find FullPageOS launch script to patch"
    echo "  The /etc/chromium.d/ approach should still work"
fi

# === FIX 3: Preferences JSON as defense in depth ===
mkdir -p $CHROMIUM_HOME/.config/chromium/Default
cat > $CHROMIUM_HOME/.config/chromium/Default/Preferences <<'PREFS_EOF'
{
   "translate": {
      "enabled": false
   },
   "translate_blocked_languages": ["af","am","ar","az","be","bg","bn","bs","ca","ceb","co","cs","cy","da","de","el","en","eo","es","et","eu","fa","fi","fr","fy","ga","gd","gl","gu","ha","haw","hi","hmn","hr","ht","hu","hy","id","ig","is","it","iw","ja","jw","ka","kk","km","kn","ko","ku","ky","la","lb","lo","lt","lv","mg","mi","mk","ml","mn","mr","ms","mt","my","ne","nl","no","ny","pa","pl","ps","pt","ro","ru","sd","si","sk","sl","sm","sn","so","sq","sr","st","su","sv","sw","ta","te","tg","th","tl","tr","uk","ur","uz","vi","xh","yi","yo","zh-CN","zh-TW","zu"],
   "translate_site_blacklist_between": [
      {"*": "*"}
   ]
}
PREFS_EOF
chown -R $CHROMIUM_USER:$CHROMIUM_USER $CHROMIUM_HOME/.config/chromium
echo "  Created Preferences JSON for user $CHROMIUM_USER"

echo ""
echo "Step 8: Enabling CSS API service..."
systemctl enable css-agent.service
systemctl restart css-agent.service
echo "  ℹ️  Auto-update and daily reboot timers are installed but disabled"
echo "  ℹ️  Enable them via the dashboard or API as needed"

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

# Chromium translate flags are applied via /etc/chromium.d/ and launch script patching (Step 7)
echo "Chromium translate fix applied via /etc/chromium.d/, launch script patch, and Preferences JSON (Step 7)"

echo ""
echo "Step 11: Configuring HDMI for 1920x1080..."
CONFIG_FILE="/boot/firmware/config.txt"

if ! grep -q "hdmi_group=" "$CONFIG_FILE"; then
    cat >> "$CONFIG_FILE" <<HDMI_EOF

# CSS Signage: Force 1920x1080 @ 60Hz
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=82
disable_overscan=1
framebuffer_width=1920
framebuffer_height=1080
HDMI_EOF
    echo "Added 1920x1080 HDMI configuration"
else
    echo "HDMI settings already present, skipping..."
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
echo "Please restart Chromium to apply changes:"
echo "  sudo pkill chromium"
echo "  (or reboot: sudo reboot)"
