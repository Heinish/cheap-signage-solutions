import secrets

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from . import config

_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="css-session")

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


def generate_device_token() -> str:
    return secrets.token_hex(32)


def generate_pairing_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def sign_session(admin_id: int) -> str:
    return _serializer.dumps({"admin_id": admin_id})


def verify_session(token: str):
    try:
        data = _serializer.loads(token, max_age=config.SESSION_MAX_AGE_SECONDS)
        return data.get("admin_id")
    except (BadSignature, SignatureExpired):
        return None
