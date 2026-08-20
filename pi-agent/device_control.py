"""
Device control logic for the CSS Signage Pi agent.

Every action the agent can perform (change the display URL, rotate the
screen, manage the playlist, ...) lives here as a plain function. Both the
local Flask debug API (server.py) and the phone-home WebSocket client
(agent.py) call into these same functions, so there is exactly one
implementation of "what a command actually does" regardless of which
transport it arrived over.
"""

import glob as globmod
import json
import os
import socket
import subprocess
import time

import psutil

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(AGENT_DIR, 'static', 'uploads')
PLAYLIST_FOLDER = os.path.join(AGENT_DIR, 'static', 'uploads', 'playlist')
MAX_PLAYLIST_IMAGES = 20
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
CONFIG_FILE = os.environ.get('CSS_AGENT_CONFIG', '/etc/css/config.json')
FULLPAGEOS_CONFIG = '/boot/firmware/fullpageos.txt'
# Used on the Phase 5 custom image (image-builder/), where the agent owns
# the kiosk directly instead of going through FullPageOS.
CSS_KIOSK_URL_FILE = '/etc/css/display_url'


# ===== Config =====

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'name': 'Pi',
            'display_url': 'http://localhost:5000/waiting',
            'api_port': 5000,
            'mainserver_url': None,
            'device_uid': None,
            'device_token': None,
        }


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_playlist_config():
    config = load_config()
    return {
        'images': config.get('playlist_images', []),
        'display_time': config.get('playlist_display_time', 5),
        'fade_time': config.get('playlist_fade_time', 1),
        'fallback_enabled': config.get('playlist_fallback_enabled', False),
    }


def save_playlist_config(playlist):
    config = load_config()
    config['playlist_images'] = playlist.get('images', [])
    config['playlist_display_time'] = playlist.get('display_time', 5)
    config['playlist_fade_time'] = playlist.get('fade_time', 1)
    config['playlist_fallback_enabled'] = playlist.get('fallback_enabled', False)
    save_config(config)


def get_agent_version():
    try:
        version_file = os.path.join(AGENT_DIR, '..', 'VERSION')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except Exception:
        return 'unknown'


# ===== System info =====

def get_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Unknown"


def get_chromium_user():
    """Detect which user is running Chromium / the X session."""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'chromium' in line and 'chrome_crashpad_handler' not in line:
                username = line.split()[0]
                if username != 'root':
                    return username
        for line in result.stdout.split('\n'):
            if 'Xorg' in line:
                username = line.split()[0]
                if username != 'root':
                    return username
        if os.path.exists('/etc/lightdm/lightdm.conf'):
            with open('/etc/lightdm/lightdm.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('autologin-user='):
                        user = line.strip().split('=', 1)[1]
                        if user:
                            return user
        return 'pi'
    except Exception:
        return 'pi'


def get_status():
    config = load_config()
    return {
        'name': config.get('name', 'Unknown'),
        'current_url': config.get('display_url', ''),
        'version': get_agent_version(),
        'uptime': int(time.time() - psutil.boot_time()),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'temperature': get_cpu_temp(),
        'ip_address': get_ip_address(),
        'screen_rotation': config.get('screen_rotation', 0),
    }


# ===== Display control =====

def _on_fullpageos():
    """True on the legacy FullPageOS-based install, False on the Phase 5
    custom image (image-builder/), where the agent owns the kiosk itself."""
    return os.path.exists(FULLPAGEOS_CONFIG)


def restart_chromium():
    if _on_fullpageos():
        # FullPageOS's own kiosk service auto-restarts Chromium after this.
        try:
            subprocess.run(['pkill', 'chromium'], check=False, timeout=2)
            time.sleep(1)
        except Exception:
            subprocess.run(['pkill', '-9', 'chromium'], check=False)
    else:
        # We own the whole X session (css-kiosk.service) - restart it
        # outright rather than guessing whether a bare pkill will bring
        # the session back cleanly. --no-block queues the restart and
        # returns immediately instead of waiting for the full X/Chromium
        # startup (which can take 30-60s+ on real hardware) - otherwise
        # this blocks long enough that the mainserver's command timeout
        # fires before the agent can report success.
        subprocess.run(['sudo', 'systemctl', 'restart', '--no-block', 'css-kiosk.service'], check=False)
    return {'success': True, 'message': 'Browser restarted'}


def _write_kiosk_url_file(url):
    """Persist the URL for whichever kiosk backend owns the screen, without
    restarting anything (used before a reboot, or from the network-status
    monitor which restarts separately)."""
    if _on_fullpageos():
        with open(FULLPAGEOS_CONFIG, 'w') as f:
            f.write(url + '\n')
    else:
        os.makedirs(os.path.dirname(CSS_KIOSK_URL_FILE), exist_ok=True)
        with open(CSS_KIOSK_URL_FILE, 'w') as f:
            f.write(url + '\n')
    os.sync()


def update_display_url_file(url):
    """Write the new URL to whichever kiosk backend owns the screen, then
    restart it so the change takes effect."""
    _write_kiosk_url_file(url)
    restart_chromium()


def set_url(url):
    if not url:
        return {'success': False, 'error': 'URL is required'}
    config = load_config()
    config['display_url'] = url
    save_config(config)
    try:
        update_display_url_file(url)
        return {'success': True, 'message': f'URL changed to {url}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def rotate_display(rotation):
    if rotation not in (0, 90, 180, 270):
        return {'success': False, 'error': 'Invalid rotation. Must be 0, 90, 180, or 270'}

    try:
        user = get_chromium_user()
        result = subprocess.run(
            ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr'],
            capture_output=True, text=True,
        )

        display_name = None
        for line in result.stdout.split('\n'):
            if 'connected' in line:
                display_name = line.split()[0]
                break

        if not display_name:
            return {'success': False, 'error': 'Could not detect display'}

        rotation_map = {0: 'normal', 90: 'right', 180: 'inverted', 270: 'left'}
        subprocess.run(
            ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr',
             '--output', display_name, '--rotate', rotation_map[rotation]],
            check=True,
        )

        config = load_config()
        config['screen_rotation'] = rotation
        save_config(config)

        return {'success': True, 'message': f'Display rotated to {rotation}°'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def capture_screenshot_bytes():
    """Capture a screenshot and return (png_bytes, error). Tries scrot, then
    fbgrab, then scrot-as-root, applying saved rotation if needed."""
    screenshot_path = f'/tmp/css-screenshot-{int(time.time())}.png'
    user = get_chromium_user()
    xauthority = f'/home/{user}/.Xauthority'

    result = None
    try:
        result = subprocess.run(
            ['sudo', '-u', user, 'env', 'DISPLAY=:0', f'XAUTHORITY={xauthority}', 'scrot', screenshot_path],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    if result is None or result.returncode != 0:
        try:
            result = subprocess.run(['fbgrab', screenshot_path], capture_output=True, timeout=5)
        except Exception:
            pass

    if result is None or result.returncode != 0:
        try:
            result = subprocess.run(['env', 'DISPLAY=:0', 'scrot', screenshot_path], capture_output=True, timeout=5)
        except Exception:
            pass

    if result is None or result.returncode != 0:
        error_msg = result.stderr.decode('utf-8') if result and result.stderr else 'No screenshot tool succeeded'
        return None, error_msg

    try:
        config = load_config()
        rotation = config.get('screen_rotation', 0)
        if rotation:
            from PIL import Image
            img = Image.open(screenshot_path)
            pil_degrees = {90: 270, 180: 180, 270: 90}.get(rotation)
            if pil_degrees:
                img.rotate(pil_degrees, expand=True).save(screenshot_path)
    except Exception:
        pass

    try:
        with open(screenshot_path, 'rb') as f:
            data = f.read()
        return data, None
    finally:
        try:
            os.unlink(screenshot_path)
        except Exception:
            pass


# ===== System =====

def reboot():
    try:
        subprocess.Popen(['sudo', 'shutdown', '-r', '+0'])
        return {'success': True, 'message': 'System rebooting'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def update_from_git():
    try:
        git_dir = '/opt/css' if os.path.exists('/opt/css/.git') else '/opt/css-agent'
        git = ['git', '-C', git_dir, '-c', f'safe.directory={git_dir}']
        subprocess.run(git + ['fetch', 'origin', 'main'], capture_output=True, text=True, timeout=30)
        result = subprocess.run(git + ['reset', '--hard', 'origin/main'], capture_output=True, text=True, timeout=30)
        success = result.returncode == 0
        if success:
            import signal
            import threading
            threading.Timer(2, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
        return {'success': success, 'output': result.stdout + result.stderr}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _netmask_to_cidr(netmask):
    try:
        cidr = int(netmask)
        if 0 <= cidr <= 32:
            return str(cidr)
    except (ValueError, TypeError):
        pass
    try:
        return str(sum(bin(int(x)).count('1') for x in netmask.split('.')))
    except Exception:
        return '24'


def _detect_active_interface():
    try:
        result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], capture_output=True, text=True, timeout=5)
        parts = result.stdout.split()
        if 'dev' in parts:
            return parts[parts.index('dev') + 1]
    except Exception:
        pass
    return 'eth0'


def _has_nmcli():
    try:
        return subprocess.run(['which', 'nmcli'], capture_output=True).returncode == 0
    except Exception:
        return False


def configure_network(data):
    if not data:
        return {'success': False, 'error': 'Configuration data required'}

    mode = data.get('mode', 'static')
    auto_reboot = data.get('auto_reboot', True)
    interface = _detect_active_interface()
    new_ip = None

    try:
        if _has_nmcli():
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'],
                capture_output=True, text=True, timeout=5,
            )
            conn_name = interface
            for line in result.stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == interface:
                    conn_name = parts[0]
                    break

            if mode == 'dhcp':
                subprocess.run(['nmcli', 'connection', 'modify', conn_name,
                                 'ipv4.method', 'auto', 'ipv4.addresses', '',
                                 'ipv4.gateway', '', 'ipv4.dns', ''], check=True, timeout=10)
                new_ip = 'DHCP'
            else:
                if not all(k in data for k in ('ip', 'netmask', 'gateway')):
                    return {'success': False, 'error': 'ip, netmask, and gateway are required for static IP'}
                ip, gateway = data['ip'], data['gateway']
                cidr = _netmask_to_cidr(data['netmask'])
                dns = data.get('dns', '8.8.8.8')
                new_ip = ip
                subprocess.run(['nmcli', 'connection', 'modify', conn_name,
                                 'ipv4.method', 'manual', 'ipv4.addresses', f'{ip}/{cidr}',
                                 'ipv4.gateway', gateway, 'ipv4.dns', dns], check=True, timeout=10)
        else:
            if mode == 'dhcp':
                with open('/etc/dhcpcd.conf', 'w') as f:
                    f.write('# Generated by CSS Agent\n# DHCP configuration\n')
                new_ip = 'DHCP'
            else:
                if not all(k in data for k in ('ip', 'netmask', 'gateway')):
                    return {'success': False, 'error': 'ip, netmask, and gateway are required for static IP'}
                ip, gateway = data['ip'], data['gateway']
                cidr = _netmask_to_cidr(data['netmask'])
                dns = data.get('dns', '8.8.8.8')
                new_ip = ip
                with open('/etc/dhcpcd.conf', 'w') as f:
                    f.write(
                        f"# Generated by CSS Agent\n# Static IP configuration\n\n"
                        f"interface {interface}\nstatic ip_address={ip}/{cidr}\n"
                        f"static routers={gateway}\nstatic domain_name_servers={dns}\n"
                    )

        config = load_config()
        config['display_url'] = 'http://localhost:5000/waiting'
        save_config(config)
        try:
            _write_kiosk_url_file('http://localhost:5000/waiting')
        except Exception:
            pass

        response = {'success': True, 'new_ip': new_ip, 'reboot_required': True}
        if auto_reboot:
            subprocess.Popen(['sudo', 'shutdown', '-r', '+0'])
            response['message'] = f'Network configuration updated. Rebooting. Reconnect at: {new_ip}'
        else:
            response['message'] = 'Network configuration updated. Reboot required to apply.'
        return response
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_settings():
    def _timer_enabled(name):
        try:
            return subprocess.run(['systemctl', 'is-enabled', name], capture_output=True, text=True).returncode == 0
        except Exception:
            return False

    return {
        'autoupdate': {'enabled': _timer_enabled('css-auto-update.timer'), 'schedule': '02:50 daily'},
        'daily_reboot': {'enabled': _timer_enabled('css-daily-reboot.timer'), 'schedule': '03:00 daily'},
    }


def set_settings(data):
    try:
        if 'autoupdate' in data and 'enabled' in data['autoupdate']:
            action = 'enable' if data['autoupdate']['enabled'] else 'disable'
            subprocess.run(['systemctl', action, 'css-auto-update.timer'], check=True)
            subprocess.run(['systemctl', 'start' if action == 'enable' else 'stop', 'css-auto-update.timer'], check=True)

        if 'daily_reboot' in data and 'enabled' in data['daily_reboot']:
            action = 'enable' if data['daily_reboot']['enabled'] else 'disable'
            subprocess.run(['systemctl', action, 'css-daily-reboot.timer'], check=True)
            subprocess.run(['systemctl', 'start' if action == 'enable' else 'stop', 'css-daily-reboot.timer'], check=True)

        return {'success': True, 'settings': get_settings()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ===== Image display =====

def upload_image(filename, data_bytes):
    ext = filename.rsplit('.', 1)[-1].lower() if filename and '.' in filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {'success': False, 'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'}

    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        for old_file in globmod.glob(os.path.join(UPLOAD_FOLDER, 'display-image.*')):
            os.unlink(old_file)

        filepath = os.path.join(UPLOAD_FOLDER, f'display-image.{ext}')
        with open(filepath, 'wb') as f:
            f.write(data_bytes)

        image_url = 'http://localhost:5000/api/display/image/view'
        config = load_config()
        config['display_url'] = image_url
        save_config(config)
        update_display_url_file(image_url)

        return {'success': True, 'message': 'Image uploaded and displaying'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_image():
    try:
        deleted = False
        for old_file in globmod.glob(os.path.join(UPLOAD_FOLDER, 'display-image.*')):
            os.unlink(old_file)
            deleted = True
        return {'success': True, 'message': 'Image deleted' if deleted else 'No image to delete'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ===== Playlist =====

def playlist_set(data):
    playlist = get_playlist_config()
    if 'display_time' in data:
        playlist['display_time'] = max(1, int(data['display_time']))
    if 'fade_time' in data:
        playlist['fade_time'] = max(0, float(data['fade_time']))
    if 'fallback_enabled' in data:
        playlist['fallback_enabled'] = bool(data['fallback_enabled'])
    save_playlist_config(playlist)
    return {'success': True, 'playlist': playlist}


def playlist_clear():
    playlist = get_playlist_config()
    for filename in playlist['images']:
        filepath = os.path.join(PLAYLIST_FOLDER, filename)
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
        except Exception:
            pass
    playlist['images'] = []
    save_playlist_config(playlist)
    return {'success': True}


def playlist_upload_image(filename, data_bytes):
    ext = filename.rsplit('.', 1)[-1].lower() if filename and '.' in filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {'success': False, 'error': 'Invalid file type'}

    playlist = get_playlist_config()
    if len(playlist['images']) >= MAX_PLAYLIST_IMAGES:
        return {'success': False, 'error': f'Maximum {MAX_PLAYLIST_IMAGES} images reached'}

    os.makedirs(PLAYLIST_FOLDER, exist_ok=True)
    index = len(playlist['images'])
    filename = f'playlist-{index}.{ext}'
    with open(os.path.join(PLAYLIST_FOLDER, filename), 'wb') as f:
        f.write(data_bytes)

    playlist['images'].append(filename)
    save_playlist_config(playlist)
    return {'success': True, 'index': index, 'filename': filename, 'total': len(playlist['images'])}


def playlist_delete_image(index):
    playlist = get_playlist_config()
    if index < 0 or index >= len(playlist['images']):
        return {'success': False, 'error': 'Invalid index'}

    filepath = os.path.join(PLAYLIST_FOLDER, playlist['images'][index])
    try:
        if os.path.exists(filepath):
            os.unlink(filepath)
    except Exception:
        pass

    playlist['images'].pop(index)
    save_playlist_config(playlist)
    return {'success': True, 'total': len(playlist['images'])}


def start_network_monitor():
    """Background thread: show the offline page (or playlist fallback, if
    enabled) when internet connectivity drops, and restore the configured
    display URL when it comes back."""
    import threading

    def _monitor():
        offline_shown = False
        time.sleep(30)  # let the server and browser finish starting first

        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect(("8.8.8.8", 53))
                s.close()
                online = True
            except (socket.error, OSError):
                online = False

            if not online and not offline_shown:
                try:
                    pl = get_playlist_config()
                    if pl.get('fallback_enabled') and pl.get('images'):
                        fallback_url = 'http://localhost:5000/slideshow'
                    else:
                        fallback_url = 'http://localhost:5000/offline'
                    _write_kiosk_url_file(fallback_url)
                    restart_chromium()
                    offline_shown = True
                except Exception as e:
                    print(f"Failed to show fallback page: {e}")

            elif online and offline_shown:
                try:
                    config = load_config()
                    url = config.get('display_url', 'http://localhost:5000/waiting')
                    if 'offline' in url:
                        url = 'http://localhost:5000/waiting'
                    _write_kiosk_url_file(url)
                    restart_chromium()
                    offline_shown = False
                except Exception as e:
                    print(f"Failed to restore display URL: {e}")

            time.sleep(15)

    threading.Thread(target=_monitor, daemon=True, name='network-monitor').start()


def apply_saved_rotation():
    """Background thread: re-apply the saved screen rotation on boot.
    Retries because X/Chromium may not be ready yet right after startup."""
    import threading

    config = load_config()
    rotation = config.get('screen_rotation', 0)
    if not rotation:
        return

    rotation_map = {90: 'right', 180: 'inverted', 270: 'left'}
    xrandr_rotation = rotation_map.get(rotation)
    if not xrandr_rotation:
        return

    def _apply():
        for attempt in range(20):
            time.sleep(5)
            try:
                user = get_chromium_user()
                result = subprocess.run(
                    ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr'],
                    capture_output=True, text=True, timeout=5,
                )
                display_name = None
                for line in result.stdout.split('\n'):
                    if 'connected' in line:
                        display_name = line.split()[0]
                        break
                if display_name:
                    subprocess.run(
                        ['sudo', '-u', user, 'env', 'DISPLAY=:0', 'xrandr',
                         '--output', display_name, '--rotate', xrandr_rotation],
                        check=True, timeout=5,
                    )
                    print(f"Applied saved rotation: {rotation}")
                    return
            except Exception as e:
                print(f"Rotation attempt {attempt + 1}/20: {e}")

        print("Could not apply saved rotation after 20 attempts")

    threading.Thread(target=_apply, daemon=True, name='apply-rotation').start()


def playlist_activate():
    playlist = get_playlist_config()
    if not playlist['images']:
        return {'success': False, 'error': 'No images in playlist'}

    playlist_url = 'http://localhost:5000/slideshow'
    config = load_config()
    config['display_url'] = playlist_url
    save_config(config)
    try:
        update_display_url_file(playlist_url)
        return {'success': True, 'message': 'Slideshow activated'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
