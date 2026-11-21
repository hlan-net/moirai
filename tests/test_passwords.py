"""bcrypt password hashing that replaced passlib."""

from __future__ import annotations

import bcrypt

from api.passwords import hash_password, verify_password


def test_hash_and_verify_round_trip():
    hashed = hash_password("correct horse")
    assert hashed.startswith("$2b$12$")
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong", hashed)


def test_hashes_are_salted():
    first = hash_password("same")
    second = hash_password("same")
    assert first != second
    assert verify_password("same", first) and verify_password("same", second)


def test_verifies_a_hash_made_with_plain_bcrypt():
    """The stored format is standard bcrypt, whoever produced it."""
    stored = bcrypt.hashpw(b"s3cret", bcrypt.gensalt(rounds=4)).decode()
    assert verify_password("s3cret", stored)


def test_long_passwords_are_truncated_like_passlib_did():
    long_password = "x" * 100
    hashed = hash_password(long_password)  # bcrypt 5 would raise on >72 bytes
    assert verify_password(long_password, hashed)
    # Only the first 72 bytes count, as with passlib.
    assert verify_password("x" * 72, hashed)
    assert not verify_password("x" * 71, hashed)


def test_non_ascii_passwords():
    hashed = hash_password("pässwörd-äö")
    assert verify_password("pässwörd-äö", hashed)
    assert not verify_password("passwrd-ao", hashed)


def test_malformed_hash_is_a_failed_login_not_an_error():
    assert not verify_password("anything", "not-a-hash")
    # Non-ASCII garbage: UnicodeEncodeError is a ValueError, so it is caught too.
    assert not verify_password("anything", "höpö-ei-tiiviste")
    assert not verify_password("anything", "")
    assert not verify_password("anything", None)  # type: ignore[arg-type]


# Real output of ``passlib.hash.bcrypt.hash(...)`` (passlib 1.7.4, bcrypt 4.3.0),
# generated before passlib was removed. Stored hashes must keep verifying.
PASSLIB_HASH = "$2b$12$SpNi/RjlADbYfhNqi8s3huWmN.zwRsDQatjEoTD/IRGFqBl6ExLM2"
PASSLIB_HASH_OF_100_X = "$2b$12$/WgV1R9Rx1cdQ93HUjgQGOlHaHkPZPF032TxUTr72SGJ8D79tba9S"


def test_hashes_stored_by_passlib_still_verify():
    assert verify_password("correct horse", PASSLIB_HASH)
    assert not verify_password("incorrect horse", PASSLIB_HASH)


def test_long_password_stored_by_passlib_still_verifies():
    assert verify_password("x" * 100, PASSLIB_HASH_OF_100_X)
