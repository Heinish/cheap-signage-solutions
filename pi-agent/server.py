#!/usr/bin/env python3
"""
CSS Signage Agent - Flask REST API Server
Provides endpoints for managing the Raspberry Pi signage display
"""

from flask import Flask, jsonify, request, send_from_directory, redirect, send_file
import subprocess
import psutil
import os
import json
import time
import socket
from datetime import datetime
import tempfile

app = Flask(__name__, static_folder='static')
CONFIG_FILE = '/etc/css/config.json'
FULLPAGEOS_CONFIG = '/boot/firmware/fullpageos.txt'

def is_fullpageos():
    """Check if running on FullPageOS"""
    return os.path.exists(FULLPAGEOS_CONFIG)

def load_config():
    """Load configuration from file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return {
            'name': 'Pi',
            'room': '',
            'display_url': 'file:///opt/css-agent/static/waiting.html',
            'api_port': 5000
        }

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_cpu_temp():
    """Get CPU temperature in Celsius"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
            return round(temp, 1)
    except:
        return None

def get_ip_address():
    """Get the Pi's IP address"""
    try:
        # Connect to external address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Unknown"

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current Pi status including stats and configuration"""
    config = load_config()

    return jsonify({
        'name': config.get('name', 'Unknown'),
        'room': config.get('room', ''),
        'current_url': config.get('display_url', ''),
        'uptime': int(time.time() - psutil.boot_time()),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'temperature': get_cpu_temp(),
        'ip_address': get_ip_address(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    """Get or update configuration"""
    if request.method == 'GET':
        return jsonify(load_config())
    else:
        # Update configuration
        data = request.json
        config = load_config()

        # Update only provided fields
        if 'name' in data:
            config['name'] = data['name']
        if 'room' in data:
            config['room'] = data['room']
        if 'display_url' in data:
            config['display_url'] = data['display_url']
        if 'api_port' in data:
            config['api_port'] = data['api_port']

        save_config(config)
        return jsonify({'success': True, 'message': 'Configuration updated'})

@app.route('/api/display/url', methods=['POST'])
def set_url():
    """Change the displayed URL and restart browser"""
    data = request.json

    if not data or 'url' not in data:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    url = data['url']

    # Update configuration
    config = load_config()
    config['display_url'] = url
    save_config(config)

    # Restart browser to apply new URL
    try:
        if is_fullpageos():
            # FullPageOS: update config file and kill chromium
            with open(FULLPAGEOS_CONFIG, 'w') as f:
                f.write(url)
            subprocess.run(['pkill', 'chromium'], check=False)  # Don't check return code
        else:
            # Standard CSS installation: restart systemd service
            subprocess.run(['systemctl', 'restart', 'css-kiosk'], check=True)

        return jsonify({'success': True, 'message': f'URL changed to {url}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/browser/restart', methods=['POST'])
def restart_browser():
    """Restart the Chromium browser"""
    try:
        if is_fullpageos():
            # FullPageOS: kill chromium (it will auto-restart)
            subprocess.run(['pkill', 'chromium'], check=False)
        else:
            # Standard CSS installation: restart systemd service
            subprocess.run(['systemctl', 'restart', 'css-kiosk'], check=True)

        return jsonify({'success': True, 'message': 'Browser restarted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/display/screenshot', methods=['GET'])
def get_screenshot():
    """Capture screenshot of current display"""
    try:
        # Create temporary file for screenshot
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        screenshot_path = temp_file.name
        temp_file.close()

        # Detect display server and capture screenshot
        if os.environ.get('WAYLAND_DISPLAY'):
            # Wayland - use grim
            result = subprocess.run(['grim', screenshot_path], capture_output=True, timeout=5)
        else:
            # X11 - use scrot
            result = subprocess.run(['scrot', screenshot_path], capture_output=True, timeout=5)

        if result.returncode != 0:
            # Cleanup and return error
            os.unlink(screenshot_path)
            return jsonify({'success': False, 'error': 'Screenshot capture failed'}), 500

        # Send file and cleanup
        return send_file(screenshot_path, mimetype='image/png', as_attachment=True,
                        download_name='screenshot.png', max_age=0)

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Screenshot timeout'}), 500
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': 'Screenshot tool not installed (grim or scrot required)'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/display/rotate', methods=['POST'])
def rotate_display():
    """Rotate the display orientation"""
    data = request.json

    if not data or 'rotation' not in data:
        return jsonify({'success': False, 'error': 'Rotation value required (0, 90, 180, or 270)'}), 400

    rotation = data['rotation']
    if rotation not in [0, 90, 180, 270]:
        return jsonify({'success': False, 'error': 'Invalid rotation. Must be 0, 90, 180, or 270'}), 400

    try:
        # For Raspberry Pi, we modify /boot/firmware/config.txt
        config_file = '/boot/firmware/config.txt'

        # Read current config
        with open(config_file, 'r') as f:
            lines = f.readlines()

        # Remove existing display_rotate lines
        lines = [line for line in lines if not line.strip().startswith('display_rotate=')]

        # Add new rotation setting
        # display_rotate values: 0=normal, 1=90°, 2=180°, 3=270°
        rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
        lines.append(f'\n# CSS Signage - Display Rotation\ndisplay_rotate={rotation_map[rotation]}\n')

        # Write back to config
        with open(config_file, 'w') as f:
            f.writelines(lines)

        return jsonify({
            'success': True,
            'message': f'Display rotation set to {rotation}°. Reboot required to apply.',
            'reboot_required': True
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/reboot', methods=['POST'])
def reboot():
    """Reboot the Raspberry Pi"""
    try:
        # Schedule reboot in 3 seconds to allow response to be sent
        subprocess.Popen(['sudo', 'shutdown', '-r', '+0'])
        return jsonify({'success': True, 'message': 'System rebooting'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update():
    """Pull latest code from GitHub repository"""
    try:
        result = subprocess.run(
            ['git', '-C', '/opt/css-agent', 'pull'],
            capture_output=True,
            text=True,
            timeout=30
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        if success:
            # Restart the agent service to apply updates
            subprocess.run(['systemctl', 'restart', 'css-agent'])

        return jsonify({
            'success': success,
            'output': output,
            'message': 'Update successful' if success else 'Update failed'
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Update timed out'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/ip', methods=['POST'])
def configure_network():
    """Configure network IP address (static or DHCP)"""
    data = request.json

    if not data:
        return jsonify({'success': False, 'error': 'Configuration data required'}), 400

    mode = data.get('mode', 'static')  # 'static' or 'dhcp'

    try:
        if mode == 'dhcp':
            # Configure DHCP in /etc/dhcpcd.conf
            dhcpcd_config = """
# Generated by CSS Agent
# DHCP configuration
"""
            with open('/etc/dhcpcd.conf', 'w') as f:
                f.write(dhcpcd_config)

        else:  # static
            # Validate required fields
            if not all(k in data for k in ['ip', 'netmask', 'gateway']):
                return jsonify({
                    'success': False,
                    'error': 'ip, netmask, and gateway are required for static IP'
                }), 400

            ip = data['ip']
            netmask = data['netmask']
            gateway = data['gateway']
            dns = data.get('dns', '8.8.8.8')

            # Configure static IP in /etc/dhcpcd.conf
            dhcpcd_config = f"""
# Generated by CSS Agent
# Static IP configuration

interface eth0
static ip_address={ip}/{netmask}
static routers={gateway}
static domain_name_servers={dns}
"""
            with open('/etc/dhcpcd.conf', 'w') as f:
                f.write(dhcpcd_config)

        return jsonify({
            'success': True,
            'message': 'Network configuration updated. System will reboot to apply changes.',
            'note': 'You will need to reconnect using the new IP address'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/', methods=['GET'])
def index():
    """Root endpoint - redirect to waiting page"""
    return redirect('/waiting')

@app.route('/waiting', methods=['GET'])
def waiting():
    """Serve the waiting page"""
    return send_from_directory('static', 'waiting.html')

@app.route('/offline', methods=['GET'])
def offline():
    """Serve the offline page"""
    return send_from_directory('static', 'offline.html')

@app.route('/api/info', methods=['GET'])
def info():
    """API info endpoint"""
    config = load_config()
    return jsonify({
        'service': 'CSS Signage Agent',
        'version': '1.0.0',
        'name': config.get('name', 'Unknown'),
        'status': 'running'
    })

if __name__ == '__main__':
    # Load port from config
    config = load_config()
    port = config.get('api_port', 5000)

    print(f"Starting CSS Signage Agent API server on port {port}")
    print(f"Pi Name: {config.get('name', 'Unknown')}")
    print(f"Display URL: {config.get('display_url', 'Not set')}")

    # Run Flask server
    # host='0.0.0.0' allows external connections
    app.run(host='0.0.0.0', port=port, debug=False)
