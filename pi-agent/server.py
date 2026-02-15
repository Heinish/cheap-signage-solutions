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

# Disable caching for all responses
@app.after_request
def add_no_cache_headers(response):
    """Add headers to prevent caching"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
            try:
                # Write URL with newline for proper formatting
                with open(FULLPAGEOS_CONFIG, 'w') as f:
                    f.write(url + '\n')
                # Sync to ensure write completes before killing browser
                os.sync()
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to write config: {str(e)}'}), 500

            # Use SIGTERM first (graceful), then SIGKILL if needed
            try:
                subprocess.run(['pkill', 'chromium'], check=False, timeout=2)
                time.sleep(1)
            except:
                subprocess.run(['pkill', '-9', 'chromium'], check=False)
        else:
            # Standard CSS installation: try systemd service, fallback to direct kill
            result = subprocess.run(['systemctl', 'restart', 'css-kiosk'], check=False)
            if result.returncode != 0:
                # Service doesn't exist, try killing chromium directly
                subprocess.run(['pkill', 'chromium'], check=False)

        return jsonify({'success': True, 'message': f'URL changed to {url}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/browser/restart', methods=['POST'])
def restart_browser():
    """Restart the Chromium browser"""
    try:
        if is_fullpageos():
            # FullPageOS: kill chromium gracefully (it will auto-restart)
            try:
                subprocess.run(['pkill', 'chromium'], check=False, timeout=2)
                time.sleep(1)
            except:
                subprocess.run(['pkill', '-9', 'chromium'], check=False)
        else:
            # Standard CSS installation: try systemd service, fallback to direct kill
            result = subprocess.run(['systemctl', 'restart', 'css-kiosk'], check=False)
            if result.returncode != 0:
                # Service doesn't exist, try killing chromium directly
                subprocess.run(['pkill', 'chromium'], check=False)

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
            content = f.read()

        # Remove existing display_rotate and lcd_rotate lines
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if not (stripped.startswith('display_rotate=') or
                   stripped.startswith('lcd_rotate=') or
                   stripped.startswith('#display_rotate=') or
                   stripped.startswith('#lcd_rotate=')):
                filtered_lines.append(line)

        # Find [all] section or add it
        config_content = '\n'.join(filtered_lines)

        # Rotation values: 0=normal, 1=90°, 2=180°, 3=270°
        rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
        rotation_value = rotation_map[rotation]

        # Add rotation settings at the end (works for both old and new Pi)
        rotation_config = f'\n# CSS Signage - Display Rotation\ndisplay_rotate={rotation_value}\nlcd_rotate={rotation_value}\n'

        # Write back to config
        with open(config_file, 'w') as f:
            f.write(config_content.rstrip() + rotation_config)

        # Sync to disk
        os.sync()

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
        # Use /opt/css (parent repo) or /opt/css-agent if it's a direct git clone
        git_dir = '/opt/css' if os.path.exists('/opt/css/.git') else '/opt/css-agent'

        result = subprocess.run(
            ['git', '-C', git_dir, 'pull'],
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
    auto_reboot = data.get('auto_reboot', True)  # Auto-reboot by default

    new_ip = None

    try:
        if mode == 'dhcp':
            # Configure DHCP in /etc/dhcpcd.conf
            dhcpcd_config = """
# Generated by CSS Agent
# DHCP configuration
"""
            with open('/etc/dhcpcd.conf', 'w') as f:
                f.write(dhcpcd_config)

            new_ip = "DHCP"  # IP will be assigned by DHCP server

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
            new_ip = ip

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

        # Prepare response
        response_data = {
            'success': True,
            'message': 'Network configuration updated.',
            'new_ip': new_ip,
            'reboot_required': True
        }

        if auto_reboot:
            # Schedule reboot in 3 seconds to allow response to be sent
            subprocess.Popen(['sudo', 'shutdown', '-r', '+0'])
            response_data['message'] += ' System rebooting in 3 seconds.'
            response_data['note'] = f'Reconnect at new IP: {new_ip}'
        else:
            response_data['message'] += ' Reboot required to apply changes.'
            response_data['note'] = 'Manual reboot needed'

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/autoupdate', methods=['GET', 'POST'])
def autoupdate_settings():
    """Get or configure auto-update settings"""
    if request.method == 'GET':
        try:
            # Check if auto-update timer is enabled
            result = subprocess.run(
                ['systemctl', 'is-enabled', 'css-auto-update.timer'],
                capture_output=True,
                text=True
            )
            enabled = result.returncode == 0

            return jsonify({
                'enabled': enabled,
                'schedule': '02:50 daily (10 min before reboot)'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    else:  # POST
        data = request.json
        if not data or 'enabled' not in data:
            return jsonify({'success': False, 'error': 'enabled parameter required'}), 400

        try:
            if data['enabled']:
                subprocess.run(['systemctl', 'enable', 'css-auto-update.timer'], check=True)
                subprocess.run(['systemctl', 'start', 'css-auto-update.timer'], check=True)
                message = 'Auto-update enabled'
            else:
                subprocess.run(['systemctl', 'stop', 'css-auto-update.timer'], check=True)
                subprocess.run(['systemctl', 'disable', 'css-auto-update.timer'], check=True)
                message = 'Auto-update disabled'

            return jsonify({'success': True, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/reboot', methods=['GET', 'POST'])
def reboot_settings():
    """Get or configure daily reboot settings"""
    if request.method == 'GET':
        try:
            # Check if daily reboot timer is enabled
            result = subprocess.run(
                ['systemctl', 'is-enabled', 'css-daily-reboot.timer'],
                capture_output=True,
                text=True
            )
            enabled = result.returncode == 0

            return jsonify({
                'enabled': enabled,
                'schedule': '03:00 daily'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    else:  # POST
        data = request.json
        if not data or 'enabled' not in data:
            return jsonify({'success': False, 'error': 'enabled parameter required'}), 400

        try:
            if data['enabled']:
                subprocess.run(['systemctl', 'enable', 'css-daily-reboot.timer'], check=True)
                subprocess.run(['systemctl', 'start', 'css-daily-reboot.timer'], check=True)
                message = 'Daily reboot enabled'
            else:
                subprocess.run(['systemctl', 'stop', 'css-daily-reboot.timer'], check=True)
                subprocess.run(['systemctl', 'disable', 'css-daily-reboot.timer'], check=True)
                message = 'Daily reboot disabled'

            return jsonify({'success': True, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/browser/flags', methods=['POST'])
def configure_browser_flags():
    """Configure Chromium flags (FullPageOS only)"""
    if not is_fullpageos():
        return jsonify({'success': False, 'error': 'Only supported on FullPageOS'}), 400

    try:
        # Configure both boot flags and user flags
        ensure_chromium_flags()
        configure_chromium_preferences()

        # Restart browser to apply new flags
        try:
            subprocess.run(['pkill', 'chromium'], check=False, timeout=2)
        except:
            subprocess.run(['pkill', '-9', 'chromium'], check=False)

        return jsonify({
            'success': True,
            'message': 'Browser flags configured and browser restarted. Translation features should now be disabled.'
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

def ensure_chromium_flags():
    """Ensure Chromium has the correct flags to disable translation and other unwanted features"""
    if not is_fullpageos():
        return  # Only applies to FullPageOS

    flags_file = '/boot/firmware/fullpageos-flags.txt'
    required_flags = [
        '--disable-translate',
        '--disable-features=Translate',
        '--no-first-run',
        '--noerrdialogs',
        '--disable-infobars',
        '--disable-session-crashed-bubble'
    ]

    try:
        # Read existing flags if file exists
        existing_flags = []
        if os.path.exists(flags_file):
            with open(flags_file, 'r') as f:
                existing_flags = [line.strip() for line in f if line.strip()]

        # Add missing flags
        updated = False
        for flag in required_flags:
            if flag not in existing_flags:
                existing_flags.append(flag)
                updated = True

        # Write back if updated
        if updated:
            with open(flags_file, 'w') as f:
                for flag in existing_flags:
                    f.write(flag + '\n')
            os.sync()
            print(f"✅ Updated Chromium flags in {flags_file}")
            print("   Flags updated. Browser restart required to apply.")
        else:
            print(f"✅ Chromium flags already configured correctly")

    except Exception as e:
        print(f"⚠️ Warning: Could not update Chromium flags: {e}")

def get_chromium_user():
    """Detect which user is running Chromium"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'chromium' in line and 'chrome_crashpad_handler' not in line:
                # Extract username from ps output (first column)
                username = line.split()[0]
                return username
        return 'pi'  # Default fallback
    except:
        return 'pi'

def configure_chromium_preferences():
    """Configure Chromium flags to disable translation via chromium-flags.conf"""
    if not is_fullpageos():
        return  # Only applies to FullPageOS

    try:
        # Detect the user running Chromium
        user = get_chromium_user()
        config_dir = f'/home/{user}/.config'
        flags_file = f'{config_dir}/chromium-flags.conf'

        # Ensure .config directory exists
        os.makedirs(config_dir, exist_ok=True)

        # Flags to disable translation
        required_flags = [
            '--disable-features=Translate',
            '--disable-features=TranslateUI',
            '--disable-translate'
        ]

        # Read existing flags if file exists
        existing_flags = []
        if os.path.exists(flags_file):
            with open(flags_file, 'r') as f:
                existing_flags = [line.strip() for line in f if line.strip()]

        # Add missing flags
        updated = False
        for flag in required_flags:
            if flag not in existing_flags:
                existing_flags.append(flag)
                updated = True

        # Write flags file
        if updated or not os.path.exists(flags_file):
            with open(flags_file, 'w') as f:
                for flag in existing_flags:
                    f.write(flag + '\n')

            # Set correct ownership
            import pwd
            uid = pwd.getpwnam(user).pw_uid
            gid = pwd.getpwnam(user).pw_gid
            os.chown(flags_file, uid, gid)

            print(f"✅ Translate disabled in Chromium flags for user '{user}'")
            print(f"   Created: {flags_file}")
        else:
            print(f"✅ Chromium flags already configured correctly for user '{user}'")

    except Exception as e:
        print(f"⚠️ Warning: Could not configure Chromium flags: {e}")

if __name__ == '__main__':
    # Ensure Chromium flags are configured to disable translation
    ensure_chromium_flags()
    configure_chromium_preferences()  # Create chromium-flags.conf to disable translate

    # Load port from config
    config = load_config()
    port = config.get('api_port', 5000)

    print(f"Starting CSS Signage Agent API server on port {port}")
    print(f"Pi Name: {config.get('name', 'Unknown')}")
    print(f"Display URL: {config.get('display_url', 'Not set')}")

    # Run Flask server
    # host='0.0.0.0' allows external connections
    app.run(host='0.0.0.0', port=port, debug=False)
