import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialDecryptionError(RuntimeError):
    pass


def encrypt_credential(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_credential(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise CredentialDecryptionError(
            "接口密钥无法解密，请确认 AI_CONFIG_ENCRYPTION_KEY 未发生变化"
        ) from exc


def credential_hint(value: str) -> str:
    suffix = value[-4:] if len(value) >= 4 else value
    return f"••••{suffix}"


def _fernet() -> Fernet:
    material = settings.AI_CONFIG_ENCRYPTION_KEY.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)
