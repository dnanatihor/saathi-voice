"""Email and password login. The hash uses PBKDF2; the token is an HMAC."""

import hashlib
import hmac
import os
from secrets import token_hex

from sqlmodel import Session, select

from saathi.models import Caregiver, LinkCode


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", maxsplit=1)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def issue_token(caregiver_id: int, secret: str) -> str:
    payload = str(caregiver_id)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def caregiver_id_from_token(token: str, secret: str) -> int | None:
    payload, separator, signature = token.partition(".")
    if not separator or not payload.isdigit():
        return None
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return int(payload)


def issue_link_code(db: Session, caregiver_id: int) -> str:
    code = token_hex(4)
    db.add(LinkCode(code=code, caregiver_id=caregiver_id))
    db.commit()
    return code


def redeem_link_code(db: Session, code: str, chat_id: str) -> Caregiver | None:
    link = db.get(LinkCode, code)
    if link is None:
        return None
    caregiver = db.get(Caregiver, link.caregiver_id)
    if caregiver is None:
        return None
    caregiver.channel_address = chat_id
    db.add(caregiver)
    db.delete(link)
    db.commit()
    db.refresh(caregiver)
    return caregiver


def find_caregiver(db: Session, login: str) -> Caregiver | None:
    return db.exec(select(Caregiver).where(Caregiver.login == login)).first()
