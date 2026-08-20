#!/usr/bin/env python3
"""
CSS Signage Agent - local Flask API

This is now a secondary/debug interface. The primary control path is
agent.py's phone-home WebSocket client, which connects out to the
mainserver and is started as a background thread below. Both this Flask
app and agent.py call into device_control.py for the actual work, so
there's one implementation of every command regardless of which transport
it arrived over.
"""

import glob as globmod
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory, redirect, send_file, after_this_request

import agent_state
import device_control as dc

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB upload limit


def startup_cleanup():
    """Clean up disk-filling files on every startup (Chromium cache, old
    screenshots, oversized logs) so the SD card doesn't slowly fill up."""
    import glob
    import shutil
    import subprocess
    cleaned = []

    for pattern in [
        '/home/*/.config/chromium/*/Cache/*',
        '/home/*/.config/chromium/*/Code Cache/*',
        '/home/*/.config/chromium/*/GPUCache/*',
        '/home/*/.config/chromium/*/Service Worker/CacheStorage/*',
        '/home/*/.config/chromium/*/LOG*',
        '/home/*/.config/chromium/*/chrome_debug.log*',
        '/home/*/.config/chromium/Crash Reports/*',
        '/root/.config/chromium/*/Cache/*',
        '/root/.config/chromium/*/Code Cache/*',
    ]:
        for f in glob.glob(pattern):
            try:
                if os.path.isfile(f):
                    os.unlink(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors=True)
                cleaned.append(f)
            except Exception:
                pass

    for f in glob.glob('/tmp/css-screenshot-*'):
        try:
            os.unlink(f)
            cleaned.append(f)
        except Exception:
            pass

    for f in glob.glob('/tmp/*.log'):
        try:
            if os.path.isfile(f) and (time.time() - os.path.getmtime(f)) > 86400:
                os.unlink(f)
                cleaned.append(f)
        except Exception:
            pass

    try:
        subprocess.run(['apt-get', 'clean'], capture_output=True, timeout=10)
        cleaned.append('apt-cache')
    except Exception:
        pass

    try:
        subprocess.run(['journalctl', '--vacuum-size=50M', '--vacuum-time=3d'], capture_output=True, timeout=10)
        cleaned.append('journalctl')
    except Exception:
        pass

    for logfile in ['/var/log/syslog', '/var/log/daemon.log', '/var/log/kern.log',
                     '/var/log/messages', '/var/log/auth.log', '/var/log/user.log',
                     '/var/log/debug', '/var/log/Xorg.0.log']:
        try:
            if os.path.isfile(logfile) and os.path.getsize(logfile) > 10 * 1024 * 1024:
                with open(logfile, 'w') as f:
                    f.truncate(0)
                cleaned.append(logfile)
        except Exception:
            pass

    for pattern in ['/var/log/*.gz', '/var/log/*.1', '/var/log/*.2', '/var/log/*.old',
                     '/var/log/**/*.gz', '/var/log/**/*.1', '/var/log/**/*.old']:
        for f in glob.glob(pattern, recursive=True):
            try:
                os.unlink(f)
                cleaned.append(f)
            except Exception:
                pass

    if cleaned:
        print(f"Startup cleanup: removed {len(cleaned)} items")


startup_cleanup()


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ===== Status / pairing =====

@app.route('/api/status', methods=['GET'])
def get_status():
    status = dc.get_status()
    status['mainserver'] = agent_state.snapshot()
    return jsonify(status)


@app.route('/api/pair/status', methods=['GET'])
def pair_status():
    return jsonify(agent_state.snapshot())


@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'GET':
        return jsonify(dc.load_config())

    data = request.json or {}
    cfg = dc.load_config()
    for field in ('name', 'display_url', 'api_port', 'mainserver_url'):
        if field in data:
            cfg[field] = data[field]
    dc.save_config(cfg)
    return jsonify({'success': True, 'message': 'Configuration updated'})


# ===== Display control =====

@app.route('/api/display/url', methods=['POST'])
def set_url():
    data = request.json or {}
    return jsonify(dc.set_url(data.get('url')))


@app.route('/api/browser/restart', methods=['POST'])
def restart_browser():
    return jsonify(dc.restart_chromium())


@app.route('/api/display/rotate', methods=['POST'])
def rotate_display():
    data = request.json or {}
    return jsonify(dc.rotate_display(data.get('rotation')))


@app.route('/api/display/screenshot', methods=['GET'])
def get_screenshot():
    data, error = dc.capture_screenshot_bytes()
    if error:
        return jsonify({'success': False, 'error': error}), 500

    tmp_path = f'/tmp/css-screenshot-view-{int(time.time())}.png'
    with open(tmp_path, 'wb') as f:
        f.write(data)

    @after_this_request
    def cleanup(response):
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return response

    return send_file(tmp_path, mimetype='image/png', as_attachment=True, download_name='screenshot.png', max_age=0)


# ===== System =====

@app.route('/api/system/reboot', methods=['POST'])
def reboot():
    return jsonify(dc.reboot())


@app.route('/api/update', methods=['POST'])
def update():
    return jsonify(dc.update_from_git())


@app.route('/api/network/ip', methods=['POST'])
def configure_network():
    return jsonify(dc.configure_network(request.json or {}))


@app.route('/api/settings/autoupdate', methods=['GET', 'POST'])
def autoupdate_settings():
    if request.method == 'GET':
        return jsonify(dc.get_settings()['autoupdate'])
    data = request.json or {}
    return jsonify(dc.set_settings({'autoupdate': {'enabled': data.get('enabled', False)}}))


@app.route('/api/settings/reboot', methods=['GET', 'POST'])
def reboot_settings():
    if request.method == 'GET':
        return jsonify(dc.get_settings()['daily_reboot'])
    data = request.json or {}
    return jsonify(dc.set_settings({'daily_reboot': {'enabled': data.get('enabled', False)}}))


# ===== Image display =====

@app.route('/api/display/image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    return jsonify(dc.upload_image(file.filename, file.read()))


@app.route('/api/display/image/view', methods=['GET'])
def view_image():
    for ext in dc.ALLOWED_IMAGE_EXTENSIONS:
        filepath = os.path.join(dc.UPLOAD_FOLDER, f'display-image.{ext}')
        if os.path.exists(filepath):
            return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="google" content="notranslate">
<style>
* {{ margin: 0; padding: 0; }}
body {{ background: #000; display: flex; align-items: center; justify-content: center;
       width: 100vw; height: 100vh; overflow: hidden; }}
img {{ max-width: 100vw; max-height: 100vh; object-fit: contain; }}
</style>
</head>
<body><img src="/static/uploads/display-image.{ext}" alt=""></body>
</html>''', 200, {'Content-Type': 'text/html'}
    return jsonify({'success': False, 'error': 'No image uploaded'}), 404


@app.route('/api/display/image', methods=['DELETE'])
def delete_image():
    return jsonify(dc.delete_image())


# ===== Playlist =====

@app.route('/api/display/playlist', methods=['GET', 'POST', 'DELETE'])
def playlist_api():
    if request.method == 'GET':
        return jsonify(dc.get_playlist_config())
    if request.method == 'DELETE':
        return jsonify(dc.playlist_clear())
    return jsonify(dc.playlist_set(request.json or {}))


@app.route('/api/display/playlist/images', methods=['POST'])
def upload_playlist_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400
    file = request.files['image']
    return jsonify(dc.playlist_upload_image(file.filename, file.read()))


@app.route('/api/display/playlist/images/<int:index>', methods=['DELETE'])
def delete_playlist_image(index):
    return jsonify(dc.playlist_delete_image(index))


@app.route('/api/display/playlist/activate', methods=['POST'])
def activate_playlist():
    return jsonify(dc.playlist_activate())


@app.route('/slideshow', methods=['GET'])
def slideshow():
    playlist = dc.get_playlist_config()
    images = playlist['images']
    display_time = playlist['display_time']
    fade_time = playlist['fade_time']

    if not images:
        return '''<!DOCTYPE html><html><body style="background:#000;color:#fff;display:flex;
align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:24px;">
<p>No images in playlist</p></body></html>''', 200, {'Content-Type': 'text/html'}

    slides_html = '\n'.join(
        f'<div class="slide" id="slide{i}"><img src="/static/uploads/playlist/{img}" alt=""></div>'
        for i, img in enumerate(images)
    )
    interval_ms = int((display_time + fade_time) * 1000)

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="google" content="notranslate">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #000; width: 100vw; height: 100vh; overflow: hidden; position: relative; }}
.slide {{
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; transition: opacity {fade_time}s ease-in-out;
}}
.slide.active {{ opacity: 1; }}
img {{ max-width: 100vw; max-height: 100vh; object-fit: contain; }}
</style>
</head>
<body>
{slides_html}
<script>
var slides = document.querySelectorAll('.slide');
var current = 0;
function next() {{
    slides.forEach(function(s) {{ s.classList.remove('active'); }});
    current = (current + 1) % slides.length;
    slides[current].classList.add('active');
}}
slides[0].classList.add('active');
setInterval(next, {interval_ms});
</script>
</body>
</html>''', 200, {'Content-Type': 'text/html'}


# ===== Static / info pages =====

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})


@app.route('/', methods=['GET'])
def index():
    return redirect('/waiting')


@app.route('/waiting', methods=['GET'])
def waiting():
    return send_from_directory('static', 'waiting.html')


@app.route('/offline', methods=['GET'])
def offline():
    return send_from_directory('static', 'offline.html')


@app.route('/api/info', methods=['GET'])
def info():
    config = dc.load_config()
    return jsonify({'service': 'CSS Signage Agent', 'version': dc.get_agent_version(), 'name': config.get('name', 'Unknown')})


# ===== Chromium setup (runs once at startup) =====

def configure_chromium_preferences():
    """Configure Chromium to disable translation via /etc/chromium.d/ and
    Preferences JSON, and patch FullPageOS's launch script if present.
    This whole function goes away once the Phase 5 custom image ships,
    since the agent will own its own kiosk launch script instead of
    patching a third party's."""
    import json
    try:
        user = dc.get_chromium_user()

        chromiumd_dir = '/etc/chromium.d'
        os.makedirs(chromiumd_dir, exist_ok=True)
        with open(os.path.join(chromiumd_dir, '99-css-disable-translate'), 'w') as f:
            f.write('# CSS Signage: Disable Chromium translate popup\n'
                    'export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disable-features=Translate,TranslateUI --disable-translate"\n')

        cache_limit_file = os.path.join(chromiumd_dir, '50-css-cache-limit')
        if not os.path.exists(cache_limit_file):
            with open(cache_limit_file, 'w') as f:
                f.write('# CSS Signage: Limit disk cache to 50MB\n'
                        'export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disk-cache-size=52428800 --media-cache-size=52428800"\n')

        import glob as g
        for pattern in [f'/home/{user}/scripts/start_chromium_browser',
                        '/home/*/scripts/start_chromium_browser',
                        '/opt/custompios/scripts/start_chromium_browser',
                        '/opt/fullpageos/scripts/start_chromium_browser']:
            for launch_script in g.glob(pattern):
                if os.path.isfile(launch_script):
                    with open(launch_script, 'r') as f:
                        content = f.read()
                    if '--disable-features=TranslateUI' in content and '--disable-features=Translate,TranslateUI' not in content:
                        content = content.replace('--disable-features=TranslateUI', '--disable-features=Translate,TranslateUI')
                        with open(launch_script, 'w') as f:
                            f.write(content)

        prefs_dir = f'/home/{user}/.config/chromium/Default'
        prefs_file = os.path.join(prefs_dir, 'Preferences')
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)
                if prefs.get('translate', {}).get('enabled') is not False:
                    prefs.setdefault('translate', {})['enabled'] = False
                    with open(prefs_file, 'w') as f:
                        json.dump(prefs, f, indent=2)
                    import pwd
                    pw = pwd.getpwnam(user)
                    os.chown(prefs_file, pw.pw_uid, pw.pw_gid)
            except Exception as e:
                print(f'Warning: could not update Preferences JSON: {e}')
    except Exception as e:
        print(f'Warning: could not configure Chromium: {e}')


def ensure_display_resolution():
    xorg_dir = '/usr/share/X11/xorg.conf.d'
    conf_file = os.path.join(xorg_dir, '10-resolution.conf')
    if not os.path.exists(conf_file):
        try:
            os.makedirs(xorg_dir, exist_ok=True)
            with open(conf_file, 'w') as f:
                f.write('Section "Screen"\n  Identifier "HDMI-1"\n  SubSection "Display"\n'
                        '    Modes "1920x1080"\n  EndSubSection\nEndSection\n')
        except Exception as e:
            print(f'Could not create resolution config: {e}')


def start_agent_thread():
    """Runs agent.py's phone-home WebSocket client in a background thread
    with its own asyncio event loop, so it doesn't block the Flask app."""
    import asyncio
    import agent as phone_home

    def _run():
        asyncio.run(phone_home.main())

    threading.Thread(target=_run, daemon=True, name='mainserver-agent').start()


if __name__ == '__main__':
    configure_chromium_preferences()
    ensure_display_resolution()

    config = dc.load_config()
    port = config.get('api_port', 5000)

    print(f"Starting CSS Signage local API on port {port}")
    print(f"Pi Name: {config.get('name', 'Unknown')}")

    dc.apply_saved_rotation()
    dc.start_network_monitor()
    start_agent_thread()

    app.run(host='0.0.0.0', port=port, debug=False)
