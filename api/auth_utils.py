import os
import jwt
import logging
import base64
import secrets
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = secrets.token_urlsafe(64)
    logger.warning("JWT_SECRET_KEY not set; using ephemeral key.")

JWT_ALGORITHM = "HS256"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def verify_basic_auth(username: str, password: str) -> Optional[Dict[str, str]]:
    if ADMIN_USERNAME and ADMIN_PASSWORD:
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return {
                "sub": "system",
                "email": f"{ADMIN_USERNAME}@localhost.local",
                "role": "admin"
            }
    return None

def parse_basic_auth(auth_header: str) -> Optional[Tuple[str, str]]:
    try:
        encoded_creds = auth_header.split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
        if ":" in decoded_creds:
            username, password = decoded_creds.split(":", 1)
            return username, password
    except Exception:
        pass
    return None

def verify_auth_header(auth_header: Optional[str]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Common logic to verify Authorization header (Bearer or Basic).
    Returns (success, error_message, user_payload).
    """
    if not auth_header:
        return False, "Authorization header is missing", None

    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_token(token)
        if not payload:
            return False, "Token is invalid or expired", None
        return True, None, payload

    if auth_header.startswith("Basic "):
        creds = parse_basic_auth(auth_header)
        if creds:
            user_info = verify_basic_auth(creds[0], creds[1])
            if user_info:
                return True, None, user_info
        return False, "Invalid Basic Auth credentials", None

    return False, "Invalid Authorization scheme", None
