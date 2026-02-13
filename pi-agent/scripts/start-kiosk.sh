#!/bin/bash
#
# CSS Signage - Kiosk Startup Script
# Launches Chromium browser in kiosk mode with the configured URL
#

CONFIG_FILE="/etc/css/config.json"
DEFAULT_URL="file:///opt/css-agent/static/waiting.html"

# Read URL from configuration file
if [ -f "$CONFIG_FILE" ]; then
    URL=$(jq -r '.display_url // "'"$DEFAULT_URL"'"' "$CONFIG_FILE")
else
    URL="$DEFAULT_URL"
fi

echo "CSS Kiosk starting with URL: $URL"

# Disable screen blanking and power management
xset s off
xset -dpms
xset s noblank

# Remove any crash flags from previous sessions
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' ~/.config/chromium/Default/Preferences 2>/dev/null
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' ~/.config/chromium/Default/Preferences 2>/dev/null

# Launch Chromium in kiosk mode
chromium "$URL" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --enable-features=OverlayScrollbar \
  --disable-session-crashed-bubble \
  --disable-component-update \
  --check-for-update-interval=31536000 \
  --disable-translate \
  --disable-features=TranslateUI \
  --disable-sync \
  --disable-background-networking \
  --disable-backgrounding-occluded-windows \
  --no-default-browser-check \
  --autoplay-policy=no-user-gesture-required \
  --disable-pinch \
  --overscroll-history-navigation=0
