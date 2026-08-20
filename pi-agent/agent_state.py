"""Tiny in-process shared state between the Flask debug API (server.py) and
the phone-home WebSocket client (agent.py), which run as threads in the same
process. Just enough for the local waiting page to show pairing progress."""
import threading

_lock = threading.Lock()
_state = {
    'mainserver_status': 'starting',  # starting | pairing | connecting | connected | disconnected
    'pairing_code': None,
}


def set_status(status: str):
    with _lock:
        _state['mainserver_status'] = status


def set_pairing_code(code):
    with _lock:
        _state['pairing_code'] = code


def snapshot():
    with _lock:
        return dict(_state)
