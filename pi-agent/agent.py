"""
Phone-home WebSocket client. This is the primary control path: the Pi
connects out to the mainserver (works from any network, no port-forwarding),
pairs once via a short code, then holds a persistent connection open to send
heartbeats and receive commands.

Every command is executed by calling into device_control.py - the same
functions the local Flask debug API in server.py uses - so there is one
implementation of "what a command does" regardless of transport.
"""
import asyncio
import base64
import json
import urllib.error
import urllib.request
import uuid

import websockets

import agent_state
import device_control

HEARTBEAT_INTERVAL_SECONDS = 15
PAIR_POLL_INTERVAL_SECONDS = 3
RECONNECT_MIN_SECONDS = 2
RECONNECT_MAX_SECONDS = 30


def _http_post_json(url, payload, timeout=10):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


async def ensure_paired():
    """Blocks until this device has a mainserver auth token, showing a
    pairing code on the local waiting page in the meantime."""
    config = device_control.load_config()

    if config.get('device_token') and config.get('mainserver_url'):
        return config

    if not config.get('device_uid'):
        config['device_uid'] = uuid.uuid4().hex
        device_control.save_config(config)

    agent_state.set_status('pairing')

    while True:
        config = device_control.load_config()
        mainserver_url = (config.get('mainserver_url') or '').rstrip('/')

        if not mainserver_url:
            print('agent: no mainserver_url configured yet, waiting...')
            await asyncio.sleep(10)
            continue

        try:
            result = _http_post_json(
                f'{mainserver_url}/api/pair/request',
                {'device_uid': config['device_uid']},
            )
        except (urllib.error.URLError, OSError) as e:
            print(f'agent: pairing request failed ({e}), retrying...')
            await asyncio.sleep(PAIR_POLL_INTERVAL_SECONDS * 2)
            continue

        if result.get('status') == 'paired':
            config['device_token'] = result['token']
            device_control.save_config(config)
            agent_state.set_pairing_code(None)
            return config

        agent_state.set_pairing_code(result.get('code'))
        await asyncio.sleep(PAIR_POLL_INTERVAL_SECONDS)


def _decode_image_param(params):
    return base64.b64decode(params.get('data_base64', ''))


ACTIONS = {
    'set_url': lambda p: device_control.set_url(p.get('url')),
    'restart_browser': lambda p: device_control.restart_chromium(),
    'rotate': lambda p: device_control.rotate_display(p.get('rotation')),
    'reboot': lambda p: device_control.reboot(),
    'update': lambda p: device_control.update_from_git(),
    'network_config': lambda p: device_control.configure_network(p),
    'get_settings': lambda p: {'success': True, 'settings': device_control.get_settings()},
    'set_settings': lambda p: device_control.set_settings(p),
    'image_upload': lambda p: device_control.upload_image(p.get('filename'), _decode_image_param(p)),
    'image_delete': lambda p: device_control.delete_image(),
    'playlist_get': lambda p: {'success': True, **device_control.get_playlist_config()},
    'playlist_set': lambda p: device_control.playlist_set(p),
    'playlist_clear': lambda p: device_control.playlist_clear(),
    'playlist_image_upload': lambda p: device_control.playlist_upload_image(p.get('filename'), _decode_image_param(p)),
    'playlist_image_delete': lambda p: device_control.playlist_delete_image(p.get('index')),
    'playlist_activate': lambda p: device_control.playlist_activate(),
}


def _run_screenshot():
    data, error = device_control.capture_screenshot_bytes()
    if error:
        return {'success': False, 'error': error}
    return {'success': True, 'image_base64': base64.b64encode(data).decode()}


async def handle_command(ws, message):
    action = message.get('action')
    params = message.get('params') or {}
    request_id = message.get('request_id')

    try:
        if action == 'screenshot':
            result = await asyncio.get_event_loop().run_in_executor(None, _run_screenshot)
        elif action in ACTIONS:
            result = await asyncio.get_event_loop().run_in_executor(None, ACTIONS[action], params)
        else:
            result = {'success': False, 'error': f'Unknown action: {action}'}
    except Exception as e:
        result = {'success': False, 'error': str(e)}

    result['type'] = 'result'
    result['request_id'] = request_id
    await ws.send(json.dumps(result))


async def heartbeat_loop(ws):
    while True:
        try:
            status = await asyncio.get_event_loop().run_in_executor(None, device_control.get_status)
            await ws.send(json.dumps({'type': 'heartbeat', 'status': status}))
        except Exception as e:
            print(f'agent: heartbeat failed: {e}')
            return
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def run_once(config):
    mainserver_url = config['mainserver_url'].rstrip('/')
    ws_url = mainserver_url.replace('http://', 'ws://').replace('https://', 'wss://')
    uri = f"{ws_url}/ws/agent?token={config['device_token']}"

    agent_state.set_status('connecting')
    async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
        agent_state.set_status('connected')
        print('agent: connected to mainserver')

        hb_task = asyncio.create_task(heartbeat_loop(ws))
        try:
            async for raw in ws:
                message = json.loads(raw)
                if message.get('type') == 'command':
                    asyncio.create_task(handle_command(ws, message))
        finally:
            hb_task.cancel()


async def main():
    backoff = RECONNECT_MIN_SECONDS
    while True:
        config = await ensure_paired()
        try:
            await run_once(config)
            backoff = RECONNECT_MIN_SECONDS
        except Exception as e:
            print(f'agent: disconnected ({e}), reconnecting in {backoff}s')
        agent_state.set_status('disconnected')
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)


if __name__ == '__main__':
    asyncio.run(main())
