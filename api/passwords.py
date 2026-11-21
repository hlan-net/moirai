"""Password hashing with bcrypt.

Replaces ``passlib.hash.bcrypt``: passlib 1.7.4 is unmaintained, breaks with
bcrypt 5 (it reads ``bcrypt.__about__``) and imports the ``crypt`` module that
Python 3.13 removed. The hashes are the same ``$2b$`` format, so everything
stored by passlib keeps verifying.
"""

import bcrypt

# bcrypt reads at most 72 bytes of a password. passlib truncated longer input
# silently; bcrypt 5 raises instead. Truncating here keeps both behaviours
# identical, so a long password hashed before this change still verifies.
_BCRYPT_MAX_BYTES = 72

# passlib's default cost; kept so new hashes match the stored ones.
_ROUNDS = 12


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a ``$2b$`` bcrypt hash of ``password``."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt(rounds=_ROUNDS)).decode(
        "ascii"
    )


def verify_password(password: str, hashed: str) -> bool:
    """True when ``password`` matches ``hashed``; False for a malformed hash."""
    try:
        return bcrypt.checkpw(_encode(password), hashed.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError, AttributeError):
        return False
