import os
import secrets
from pathlib import Path

DATA_DIR = Path(os.environ.get("CSS_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("CSS_DATABASE_URL", f"sqlite:///{DATA_DIR / 'mainserver.db'}")

# Persisted so restarting the server doesn't invalidate every session cookie.
_SECRET_FILE = DATA_DIR / "secret.key"
if os.environ.get("CSS_SECRET_KEY"):
    SECRET_KEY = os.environ["CSS_SECRET_KEY"]
elif _SECRET_FILE.exists():
    SECRET_KEY = _SECRET_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    _SECRET_FILE.write_text(SECRET_KEY)

SESSION_COOKIE_NAME = "css_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

# How long a device can go without a heartbeat before it's considered offline
DEVICE_OFFLINE_AFTER_SECONDS = 45

# How long an unclaimed pairing request stays valid
PAIRING_TTL_SECONDS = 60 * 15

# Timeout waiting for a device to respond to a forwarded command
COMMAND_TIMEOUT_SECONDS = 20

HOST = os.environ.get("CSS_HOST", "0.0.0.0")
PORT = int(os.environ.get("CSS_PORT", "8000"))
