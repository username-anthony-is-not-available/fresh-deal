"""Secure environment variable and secret management utilities (Issue #390)."""

from __future__ import annotations

import argparse
from cryptography.fernet import Fernet, InvalidToken
import logging
import os
from pathlib import Path
import re
import secrets as std_secrets
from typing import Any, Dict, Iterable, Optional

ENC_PREFIX = "enc:"

DEFAULT_INSECURE_SECRET_KEYS = frozenset({"a_very_secret_key", "secret", "changeme", "dev-secret"})
DEFAULT_INSECURE_ENCRYPTION_KEY = "VQZJVhu2seQqq4ZOM_KlwxbqOE0WOf1070WURHeJABQ="
DEFAULT_INSECURE_DB_PASSWORDS = frozenset({"postgres", "password", "changeme", ""})

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "SECRET_KEY",
        "ENCRYPTION_KEY",
        "OPENROUTER_API_KEY",
        "FATSECRET_API_KEY",
        "FATSECRET_API_SECRET",
        "EDAMAM_APP_ID",
        "EDAMAM_APP_KEY",
        "POSTGRES_PASSWORD",
        "SMTP_PASSWORD",
        "SENTRY_DSN",
        "DATABASE_URL",
        "REDIS_URL",
        "WEBHOOK_URL",
    }
)

_URI_PASSWORD_RE = re.compile(r"((?:postgres(?:ql)?|redis|rediss|smtp|https?)://[^:/@\s]*:)([^@\s]+)(@)")
_BEARER_RE = re.compile(r"(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE)
_API_TOKEN_RE = re.compile(r"\b(sk-(?:or-v1-)?[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{16,})\b")


def generate_secret_key(num_bytes: int = 32) -> str:
    """Generate a cryptographically strong URL-safe secret key."""
    return std_secrets.token_urlsafe(num_bytes)


def generate_fernet_key() -> str:
    """Generate a valid base64-encoded 32-byte Fernet encryption key."""
    return Fernet.generate_key().decode("ascii")


def _get_master_key(explicit_key: Optional[str] = None) -> str:
    key = explicit_key or os.environ.get("APP_MASTER_KEY") or os.environ.get("ENV_MASTER_KEY")
    if not key:
        raise ValueError(
            "APP_MASTER_KEY or ENV_MASTER_KEY must be set to encrypt/decrypt 'enc:' environment secrets."
        )
    return key


def encrypt_env_value(plaintext: str, master_key: Optional[str] = None) -> str:
    """Encrypt a plaintext secret into an 'enc:<token>' value safe for .env storage."""
    key = _get_master_key(master_key)
    token = Fernet(key.encode("ascii")).encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_env_value(value: str, master_key: Optional[str] = None) -> str:
    """Decrypt an 'enc:<token>' environment variable value."""
    if not value.startswith(ENC_PREFIX):
        return value
    key = _get_master_key(master_key)
    token = value[len(ENC_PREFIX) :]
    try:
        return Fernet(key.encode("ascii")).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Failed to decrypt encrypted environment variable: invalid key or token.") from exc


def resolve_env_secret(
    name: str,
    value: Optional[str],
    master_key: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve an environment secret supporting:
    1. Docker/Kubernetes mounted secret files via '<NAME>_FILE'
    2. Encrypted values prefixed with 'enc:' using APP_MASTER_KEY/ENV_MASTER_KEY
    """
    file_env = os.environ.get(f"{name}_FILE")
    if file_env:
        secret_path = Path(file_env)
        if not secret_path.is_file():
            raise ValueError(f"Secret file configured by {name}_FILE does not exist: {file_env}")
        value = secret_path.read_text(encoding="utf-8").strip()

    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        return decrypt_env_value(value, master_key=master_key)

    return value


def is_valid_fernet_key(value: Optional[str]) -> bool:
    """Return True if value is a valid Fernet key."""
    if not value:
        return False
    try:
        Fernet(value.encode("ascii"))
        return True
    except Exception:
        return False


def mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask a secret value for safe diagnostics output."""
    if not value:
        return "<unset>"
    if len(value) <= visible_chars * 2:
        return "****"
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


def redact_url_credentials(url: Optional[str]) -> Optional[str]:
    """Redact passwords embedded in connection URLs while preserving host/path."""
    if not url:
        return url
    return _URI_PASSWORD_RE.sub(r"\1****\3", url)


def sanitize_log_text(text: str, known_secrets: Iterable[str] = ()) -> str:
    """Scrub URL passwords, Bearer tokens, API keys, and known runtime secrets from log strings."""
    if not text:
        return text
    sanitized = _URI_PASSWORD_RE.sub(r"\1****\3", text)
    sanitized = _BEARER_RE.sub(r"\1****", sanitized)
    sanitized = _API_TOKEN_RE.sub("****", sanitized)
    for secret in known_secrets:
        if secret and len(secret) >= 6 and secret in sanitized:
            sanitized = sanitized.replace(secret, "****")
    return sanitized


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts credentials and configured secret values."""

    def __init__(self, extra_secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._extra_secrets = tuple(s for s in extra_secrets if s and len(s) >= 6)

    def _active_secrets(self) -> tuple[str, ...]:
        env_secrets = (
            os.environ.get(name, "")
            for name in SENSITIVE_FIELD_NAMES
            if name not in {"DATABASE_URL", "REDIS_URL", "SENTRY_DSN", "WEBHOOK_URL"}
        )
        return tuple(s for s in (*self._extra_secrets, *env_secrets) if s and len(s) >= 6)

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = self._active_secrets()
        if isinstance(record.msg, str):
            record.msg = sanitize_log_text(record.msg, secrets)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_log_text(a, secrets) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: sanitize_log_text(v, secrets) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


def build_redacted_summary(settings_obj: Any) -> Dict[str, Any]:
    """Return a diagnostics dictionary with all sensitive settings masked."""
    summary: Dict[str, Any] = {}
    for field_name in type(settings_obj).model_fields:
        val = getattr(settings_obj, field_name, None)
        if field_name in {"DATABASE_URL", "REDIS_URL", "SENTRY_DSN", "WEBHOOK_URL"}:
            summary[field_name] = redact_url_credentials(val) if isinstance(val, str) else None
        elif field_name in SENSITIVE_FIELD_NAMES:
            summary[field_name] = mask_secret(val) if isinstance(val, str) else "<unset>"
        else:
            summary[field_name] = val
    return summary


def main() -> None:
    """CLI utility for generating keys and encrypting .env secrets."""
    parser = argparse.ArgumentParser(description="Fresh Deal secret management helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate-keys", help="Generate SECRET_KEY, ENCRYPTION_KEY, and APP_MASTER_KEY")
    enc = sub.add_parser("encrypt", help="Encrypt a secret value as 'enc:<token>'")
    enc.add_argument("value", help="Plaintext value to encrypt")
    enc.add_argument("--master-key", default=None, help="Fernet master key (defaults to APP_MASTER_KEY)")

    args = parser.parse_args()
    if args.command == "generate-keys":
        print(f"SECRET_KEY={generate_secret_key()}")
        print(f"ENCRYPTION_KEY={generate_fernet_key()}")
        print(f"APP_MASTER_KEY={generate_fernet_key()}")
    elif args.command == "encrypt":
        print(encrypt_env_value(args.value, master_key=args.master_key))


if __name__ == "__main__":
    main()
