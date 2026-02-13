# CSS - Cheap Signage Solutions

A complete Raspberry Pi-based digital signage system with centralized management dashboard.

## 🎯 Project Overview

CSS (Cheap Signage Solutions) allows you to turn Raspberry Pi devices into dedicated signage displays that can be centrally managed from a Windows dashboard application. Perfect for retail displays, information boards, conference rooms, and digital menu boards.

## ✨ Features

### Raspberry Pi Agent
- **Kiosk Mode**: Full-screen Chromium browser displaying configured URLs
- **REST API**: Control Pi remotely via HTTP endpoints
- **Auto-Recovery**: Systemd services automatically restart on failure
- **Daily Reboot**: Scheduled reboot every day at 3:00 AM for stability
- **Offline Handling**: Shows offline page when network is unavailable
- **Network Configuration**: Change Pi's IP address remotely
- **Auto-Updates**: Pull latest code from GitHub repository

### Dashboard (Coming in Phase 2)
- **Multi-Pi Management**: Control multiple Pis from one interface
- **Real-time Monitoring**: CPU, memory, uptime, and temperature stats
- **Bulk Operations**: Update URLs, restart, or reboot multiple Pis at once
- **Room Organization**: Group Pis by location/room
- **URL Preview**: Screenshot preview of what each Pi is displaying
- **Auto-Updates**: Automatically update from GitHub releases

## 📋 Requirements

### Hardware
- Raspberry Pi 4 (recommended) or Pi 3
- MicroSD card (16GB minimum, 32GB recommended)
- Display with HDMI input
- Ethernet connection (or WiFi)

### Software
- Raspberry Pi OS (Debian-based)
- Python 3.7+
- Chromium browser

## 🚀 Quick Start

### Option 1: Manual Installation (Current)

1. **Flash Raspberry Pi OS (WITH DESKTOP)**
   ```bash
   # Use Raspberry Pi Imager to flash Raspberry Pi OS (64-bit) WITH DESKTOP
   # ⚠️ IMPORTANT: Do NOT use "Lite" - you need the full version with desktop!
   # Enable SSH and configure WiFi if needed in the imager settings
   ```

2. **Clone this repository on the Pi**
   ```bash
   git clone https://github.com/your-org/css.git
   cd css/pi-agent
   ```

3. **Run installation script**
   ```bash
   sudo ./scripts/install.sh
   ```

4. **Reboot**
   ```bash
   sudo reboot
   ```

5. **The Pi will boot into kiosk mode!**

### Option 2: Custom Image (Phase 4 - Coming Soon)

Download pre-built image, flash to SD card, and boot!

## 🔧 Configuration

### Pi Configuration File
Location: `/etc/css/config.json`

```json
{
  "name": "Conference Room A",
  "room": "Building 1",
  "display_url": "https://your-signage-url.com",
  "api_port": 5000
}
```

Edit this file to customize your Pi's settings, or use the dashboard to manage it remotely.

## 📡 REST API Endpoints

Base URL: `http://{pi-ip}:5000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get current status and stats |
| `/api/config` | GET | Get configuration |
| `/api/config` | POST | Update configuration |
| `/api/display/url` | POST | Change displayed URL |
| `/api/display/screenshot` | GET | Capture screenshot of current display |
| `/api/display/rotate` | POST | Rotate display (0, 90, 180, 270 degrees) |
| `/api/browser/restart` | POST | Restart Chromium browser |
| `/api/system/reboot` | POST | Reboot the Pi |
| `/api/update` | POST | Pull updates from GitHub |
| `/api/network/ip` | POST | Configure network IP |
| `/api/settings/autoupdate` | GET/POST | Get or enable/disable auto-updates |
| `/api/settings/reboot` | GET/POST | Get or enable/disable daily reboot |
| `/api/health` | GET | Health check |

### Example API Calls

**Get status:**
```bash
curl http://192.168.1.100:5000/api/status
```

**Change URL:**
```bash
curl -X POST http://192.168.1.100:5000/api/display/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Restart browser:**
```bash
curl -X POST http://192.168.1.100:5000/api/browser/restart
```

**Reboot Pi:**
```bash
curl -X POST http://192.168.1.100:5000/api/system/reboot
```

**Get screenshot:**
```bash
curl http://192.168.1.100:5000/api/display/screenshot -o screenshot.png
```

**Rotate display:**
```bash
curl -X POST http://192.168.1.100:5000/api/display/rotate \
  -H "Content-Type: application/json" \
  -d '{"rotation": 90}'
```

**Change network IP (Static with auto-reboot):**
```bash
curl -X POST http://192.168.1.100:5000/api/network/ip \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "static",
    "ip": "192.168.1.150",
    "netmask": "24",
    "gateway": "192.168.1.1",
    "dns": "8.8.8.8",
    "auto_reboot": true
  }'
# Pi will automatically reboot and apply new IP
# Dashboard should update the IP and wait ~30 seconds before reconnecting
```

**Change network IP (DHCP):**
```bash
curl -X POST http://192.168.1.100:5000/api/network/ip \
  -H "Content-Type: application/json" \
  -d '{"mode": "dhcp", "auto_reboot": true}'
# Pi will reboot and get IP from DHCP server
# Check router to find new IP address
```

## 🎨 Customization

### Change Displayed URL
Via API:
```bash
curl -X POST http://{pi-ip}:5000/api/display/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-url.com"}'
```

Or edit `/etc/css/config.json` and restart the browser service:
```bash
sudo systemctl restart css-kiosk
```

### Modify Default Pages
- Waiting page: `/opt/css-agent/static/waiting.html`
- Offline page: `/opt/css-agent/static/offline.html`

## 🛠️ Systemd Services

The installer creates these services:

- **css-agent.service**: Flask REST API server
- **css-kiosk.service**: Chromium browser in kiosk mode
- **css-daily-reboot.timer**: Daily reboot timer (3:00 AM)
- **css-network-monitor.service**: Network connectivity monitor (Phase 3)

### Service Management
```bash
# View status
sudo systemctl status css-agent
sudo systemctl status css-kiosk

# Start/stop services
sudo systemctl start css-agent
sudo systemctl stop css-agent

# View logs
sudo journalctl -u css-agent -f
sudo journalctl -u css-kiosk -f

# Disable daily reboot
sudo systemctl disable css-daily-reboot.timer
```

## 🐛 Troubleshooting

### Pi boots to desktop instead of kiosk mode
```bash
# Check if autostart is configured
ls -la /home/pi/.config/autostart/

# Manually start kiosk
/opt/css-agent/scripts/start-kiosk.sh
```

### API not responding
```bash
# Check if service is running
sudo systemctl status css-agent

# Check logs
sudo journalctl -u css-agent -n 50

# Restart service
sudo systemctl restart css-agent
```

### Browser shows error page
```bash
# Check kiosk service
sudo systemctl status css-kiosk

# View browser logs
sudo journalctl -u css-kiosk -n 50

# Restart browser
sudo systemctl restart css-kiosk
```

### Find Pi's IP address
```bash
# On the Pi
hostname -I

# From your network
# Use your router's admin panel or tools like Angry IP Scanner
```

## 📂 Project Structure

```
css/
├── pi-agent/              # Raspberry Pi agent code
│   ├── server.py          # Flask REST API
│   ├── requirements.txt   # Python dependencies
│   ├── scripts/
│   │   ├── start-kiosk.sh    # Kiosk startup
│   │   └── install.sh        # Installation script
│   ├── static/
│   │   ├── waiting.html      # Default page
│   │   └── offline.html      # Offline page
│   └── systemd/              # Service files
│
├── dashboard/             # Electron dashboard (Phase 2)
├── image-builder/         # Custom image builder (Phase 4)
└── docs/                  # Documentation
```

## 🗺️ Roadmap

### ✅ Phase 1: Basic Pi Kiosk Agent (Current)
- [x] Flask REST API server
- [x] Chromium kiosk mode
- [x] Systemd services
- [x] Installation script
- [x] Daily auto-reboot

### 📅 Phase 2: Dashboard MVP (Next)
- [ ] Electron desktop application
- [ ] Add/manage multiple Pis
- [ ] Send commands (URL change, restart, reboot)
- [ ] Real-time status monitoring
- [ ] MSI installer for Windows

### 📅 Phase 3: Advanced Features
- [ ] Room/group organization
- [ ] Bulk operations
- [ ] Network monitoring with auto-offline page
- [ ] URL preview screenshots
- [ ] Enhanced UI and settings

### 📅 Phase 4: Production Ready
- [ ] Custom Pi OS image builder
- [ ] Auto-updates (Pi and dashboard)
- [ ] Complete documentation
- [ ] GitHub releases
- [ ] CI/CD pipeline

## 🤝 Contributing

This is currently a private project in active development. Phase 1 is complete, Phase 2 is next!

## 📄 License

TBD

## 🙏 Acknowledgments

- Built for easy, affordable digital signage
- Powered by Raspberry Pi and Chromium
- Flask for the REST API
- Electron for the dashboard (coming soon)

---

**Status**: Phase 1 Complete ✅
**Next**: Begin Phase 2 - Dashboard Development
**Version**: 0.1.0-alpha
