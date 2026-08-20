#!/bin/sh
# Launched by css-kiosk.service via `startx`. Owns the whole X session -
# no FullPageOS, no CustomPiOS launch script to patch. The agent changes
# what's on screen by writing a new URL to $URL_FILE and restarting this
# service (systemctl restart css-kiosk.service).

xset -dpms
xset s off
xset s noblank

unclutter -idle 0.5 -root &
openbox-session &
sleep 1

URL_FILE=/etc/css/display_url
URL=$(cat "$URL_FILE" 2>/dev/null)
[ -z "$URL" ] && URL="http://localhost:5000/waiting"

exec chromium \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate,TranslateUI \
  --disable-translate \
  --disk-cache-size=52428800 \
  --media-cache-size=52428800 \
  --check-for-update-interval=31536000 \
  --no-first-run \
  --window-position=0,0 \
  "$URL"
