#!/usr/bin/env python3
"""
CSS Signage Agent - Flask REST API Server
Provides endpoints for managing the Raspberry Pi signage display
"""

from flask import Flask, jsonify, request, send_from_directory, redirect, send_file, after_this_request
from werkzeug.utils import secure_filename
import subprocess
import psutil
import os
import json
import time
import socket
from datetime import datetime
import tempfile
import glob as globmod

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB upload limit

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
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
        # Use a simple temporary path that the X user can write to
        import time
        screenshot_path = f'/tmp/css-screenshot-{int(time.time())}.png'

        # Detect display server and capture screenshot
        if os.environ.get('WAYLAND_DISPLAY'):
            # Wayland - use grim
            result = subprocess.run(['grim', screenshot_path], capture_output=True, timeout=5)
        else:
            # X11 - use the take-screenshot.sh wrapper script
            # This runs scrot as the correct user with proper DISPLAY/XAUTHORITY
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'take-screenshot.sh')
            user = get_chromium_user()

            result = subprocess.run(
                ['sudo', '-u', user, 'bash', script_path, screenshot_path],
                capture_output=True,
                timeout=5
            )

        if result.returncode != 0:
            # Log detailed error information
            error_msg = result.stderr.decode('utf-8') if result.stderr else 'No stderr output'
            print(f"❌ Screenshot failed: returncode={result.returncode}, stderr={error_msg}")
            # Cleanup and return error
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
            return jsonify({'success': False, 'error': f'Screenshot capture failed: {error_msg}'}), 500

        # Send file with callback to cleanup after sending
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(screenshot_path):
                    os.unlink(screenshot_path)
            except:
                pass
            return response

        return send_file(screenshot_path, mimetype='image/png', as_attachment=True,
                        download_name='screenshot.png', max_age=0)

    except subprocess.TimeoutExpired:
        if os.path.exists(screenshot_path):
            os.unlink(screenshot_path)
        return jsonify({'success': False, 'error': 'Screenshot timeout'}), 500
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': 'Screenshot tool not installed (grim or scrot required)'}), 500
    except Exception as e:
        if 'screenshot_path' in locals() and os.path.exists(screenshot_path):
            os.unlink(screenshot_path)
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
        # For FullPageOS with X11, use xrandr
        if is_fullpageos():
            # Get the user running X session
            user = get_chromium_user()

            # Detect primary display (run as the X user)
            result = subprocess.run(
                ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr'],
                capture_output=True,
                text=True
            )

            # Find connected display (HDMI-1, HDMI-2, etc.)
            display_name = None
            for line in result.stdout.split('\n'):
                if 'connected primary' in line or 'connected' in line:
                    display_name = line.split()[0]
                    if 'connected' in line:
                        break

            if not display_name:
                return jsonify({'success': False, 'error': 'Could not detect display'}), 500

            # Map rotation to xrandr values
            rotation_map = {
                0: 'normal',
                90: 'right',
                180: 'inverted',
                270: 'left'
            }
            xrandr_rotation = rotation_map[rotation]

            # Apply rotation using xrandr (run as the X user)
            subprocess.run(
                ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr', '--output', display_name, '--rotate', xrandr_rotation],
                check=True
            )

            # Make rotation persistent by creating autostart script
            autostart_dir = f'/home/{user}/.config/autostart'
            os.makedirs(autostart_dir, exist_ok=True)

            desktop_file = f'{autostart_dir}/css-rotation.desktop'
            desktop_content = f'''[Desktop Entry]
Type=Application
Name=CSS Display Rotation
Exec=sh -c "sleep 2 && DISPLAY=:0 xrandr --output {display_name} --rotate {xrandr_rotation}"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
'''
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)

            # Set ownership
            import pwd
            user = get_chromium_user()
            uid = pwd.getpwnam(user).pw_uid
            gid = pwd.getpwnam(user).pw_gid
            os.chown(desktop_file, uid, gid)

            return jsonify({
                'success': True,
                'message': f'Display rotated to {rotation}°. Rotation applied immediately and will persist after reboot.',
                'reboot_required': False
            })

        else:
            # Fallback to boot config for non-FullPageOS systems
            config_file = '/boot/firmware/config.txt'

            with open(config_file, 'r') as f:
                content = f.read()

            lines = content.split('\n')
            filtered_lines = []
            for line in lines:
                stripped = line.strip()
                if not (stripped.startswith('display_rotate=') or
                       stripped.startswith('lcd_rotate=') or
                       stripped.startswith('#display_rotate=') or
                       stripped.startswith('#lcd_rotate=')):
                    filtered_lines.append(line)

            config_content = '\n'.join(filtered_lines)

            rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
            rotation_value = rotation_map[rotation]

            rotation_config = f'\n# CSS Signage - Display Rotation\ndisplay_rotate={rotation_value}\nlcd_rotate={rotation_value}\n'

            with open(config_file, 'w') as f:
                f.write(config_content.rstrip() + rotation_config)

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
        # Configure chromium flags and preferences to disable translate
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

@app.route('/api/display/image', methods=['POST'])
def upload_image():
    """Upload an image to display on the Pi"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Validate extension
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'}), 400

    try:
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Remove any existing display images
        for old_file in globmod.glob(os.path.join(UPLOAD_FOLDER, 'display-image.*')):
            os.unlink(old_file)

        # Save the new image
        filename = f'display-image.{ext}'
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Update display URL to show the image
        image_url = 'http://localhost:5000/api/display/image/view'
        config = load_config()
        config['display_url'] = image_url
        save_config(config)

        # Update FullPageOS config and restart browser
        if is_fullpageos():
            try:
                with open(FULLPAGEOS_CONFIG, 'w') as f:
                    f.write(image_url + '\n')
                os.sync()
            except Exception as e:
                print(f"Warning: Could not write FullPageOS config: {e}")

            # Kill chromium to trigger restart
            try:
                subprocess.run(['pkill', 'chromium'], check=False, timeout=2)
                time.sleep(1)
            except:
                subprocess.run(['pkill', '-9', 'chromium'], check=False)
        else:
            result = subprocess.run(['systemctl', 'restart', 'css-kiosk'], check=False)
            if result.returncode != 0:
                subprocess.run(['pkill', 'chromium'], check=False)

        return jsonify({'success': True, 'message': 'Image uploaded and displaying', 'filename': filename})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/display/image/view', methods=['GET'])
def view_image():
    """Serve a fullscreen HTML page displaying the uploaded image"""
    # Find the current display image
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        filepath = os.path.join(UPLOAD_FOLDER, f'display-image.{ext}')
        if os.path.exists(filepath):
            return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="google" content="notranslate">
<style>
* {{ margin: 0; padding: 0; }}
body {{
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}}
img {{
  max-width: 100vw;
  max-height: 100vh;
  object-fit: contain;
}}
</style>
</head>
<body>
<img src="/static/uploads/display-image.{ext}" alt="">
</body>
</html>''', 200, {'Content-Type': 'text/html'}

    return jsonify({'success': False, 'error': 'No image uploaded'}), 404

@app.route('/api/display/image/current', methods=['GET'])
def get_current_image():
    """Get metadata about the currently uploaded image"""
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        filepath = os.path.join(UPLOAD_FOLDER, f'display-image.{ext}')
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            return jsonify({
                'has_image': True,
                'filename': f'display-image.{ext}',
                'size_bytes': size
            })

    return jsonify({'has_image': False})

@app.route('/api/display/image', methods=['DELETE'])
def delete_image():
    """Delete the currently uploaded image"""
    try:
        deleted = False
        for old_file in globmod.glob(os.path.join(UPLOAD_FOLDER, 'display-image.*')):
            os.unlink(old_file)
            deleted = True

        if deleted:
            return jsonify({'success': True, 'message': 'Image deleted'})
        else:
            return jsonify({'success': True, 'message': 'No image to delete'})
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

def get_chromium_user():
    """Detect which user is running Chromium / X session"""
    try:
        # Method 1: Check who's running Chromium
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'chromium' in line and 'chrome_crashpad_handler' not in line:
                username = line.split()[0]
                if username != 'root':
                    return username

        # Method 2: Check who's running Xorg
        for line in result.stdout.split('\n'):
            if 'Xorg' in line:
                username = line.split()[0]
                if username != 'root':
                    return username

        # Method 3: Check lightdm auto-login config
        if os.path.exists('/etc/lightdm/lightdm.conf'):
            with open('/etc/lightdm/lightdm.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('autologin-user='):
                        user = line.strip().split('=', 1)[1]
                        if user:
                            return user

        return 'pi'  # Final fallback
    except:
        return 'pi'

def configure_chromium_preferences():
    """Configure Chromium to disable translation via /etc/chromium.d/ and Preferences JSON"""
    if not is_fullpageos():
        return  # Only applies to FullPageOS

    try:
        user = get_chromium_user()

        # ===== PART 1: /etc/chromium.d/ (the correct Debian/Raspberry Pi OS way) =====
        # On Debian-based systems, /usr/bin/chromium-browser is a wrapper that sources
        # all files in /etc/chromium.d/ and passes CHROMIUM_FLAGS to the real binary.
        # This is the ONLY reliable way to pass flags on Raspberry Pi OS.
        chromiumd_dir = '/etc/chromium.d'
        chromiumd_file = os.path.join(chromiumd_dir, '99-css-disable-translate')
        chromiumd_content = '# CSS Signage: Disable Chromium translate popup\nexport CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disable-features=Translate,TranslateUI --disable-translate"\n'

        os.makedirs(chromiumd_dir, exist_ok=True)
        needs_update = True
        if os.path.exists(chromiumd_file):
            with open(chromiumd_file, 'r') as f:
                if f.read() == chromiumd_content:
                    needs_update = False

        if needs_update:
            with open(chromiumd_file, 'w') as f:
                f.write(chromiumd_content)
            print(f"✅ Created {chromiumd_file}")
        else:
            print(f"✅ {chromiumd_file} already configured")

        # ===== PART 2: Patch FullPageOS launch script =====
        import glob as g
        translate_flags = '--disable-features=Translate,TranslateUI --disable-translate'
        for pattern in [f'/home/{user}/scripts/start_chromium_browser',
                        '/home/*/scripts/start_chromium_browser']:
            for launch_script in g.glob(pattern):
                if os.path.isfile(launch_script):
                    with open(launch_script, 'r') as f:
                        content = f.read()
                    if 'disable-features=Translate' not in content:
                        content = content.replace('chromium-browser',
                                                  f'chromium-browser {translate_flags}')
                        with open(launch_script, 'w') as f:
                            f.write(content)
                        print(f"✅ Patched launch script: {launch_script}")

        # ===== PART 3: Modify Preferences JSON as defense in depth =====
        prefs_dir = f'/home/{user}/.config/chromium/Default'
        prefs_file = os.path.join(prefs_dir, 'Preferences')
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)

                if 'translate' not in prefs or prefs.get('translate', {}).get('enabled') != False:
                    if 'translate' not in prefs:
                        prefs['translate'] = {}
                    prefs['translate']['enabled'] = False

                    with open(prefs_file, 'w') as f:
                        json.dump(prefs, f, indent=2)

                    import pwd
                    uid = pwd.getpwnam(user).pw_uid
                    gid = pwd.getpwnam(user).pw_gid
                    os.chown(prefs_file, uid, gid)

                    print(f"✅ Translate disabled in Preferences JSON: {prefs_file}")
                else:
                    print(f"✅ Preferences JSON already has translate disabled")

            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Warning: Could not update Preferences JSON: {e}")
        else:
            print(f"ℹ️ Preferences file not found yet: {prefs_file}")

    except Exception as e:
        print(f"⚠️ Warning: Could not configure Chromium: {e}")

if __name__ == '__main__':
    # Configure Chromium to disable translation (flags + Preferences JSON)
    configure_chromium_preferences()

    # Load port from config
    config = load_config()
    port = config.get('api_port', 5000)

    print(f"Starting CSS Signage Agent API server on port {port}")
    print(f"Pi Name: {config.get('name', 'Unknown')}")
    print(f"Display URL: {config.get('display_url', 'Not set')}")

    # Run Flask server
    # host='0.0.0.0' allows external connections
    app.run(host='0.0.0.0', port=port, debug=False)
