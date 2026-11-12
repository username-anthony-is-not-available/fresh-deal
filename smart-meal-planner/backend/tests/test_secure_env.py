"""Tests for secure environment variable and secret management (Issue #390)."""

import logging
import pytest

from app.core.config import Settings
from app.core.secrets import (
    SecretRedactionFilter,
    decrypt_env_value,
    encrypt_env_value,
    generate_fernet_key,
    generate_secret_key,
    mask_secret,
    redact_url_credentials,
    sanitize_log_text,
)


def test_encrypted_env_value_roundtrip_and_invalid_key():
    """Encrypted 'enc:' env values decrypt with matching master key and reject wrong keys."""
    master_key = generate_fernet_key()
    wrong_key = generate_fernet_key()

    encrypted = encrypt_env_value("super-secret-api-token", master_key=master_key)
    assert encrypted.startswith("enc:")
    assert "super-secret-api-token" not in encrypted
    assert decrypt_env_value(encrypted, master_key=master_key) == "super-secret-api-token"

    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_env_value(encrypted, master_key=wrong_key)


def test_settings_resolves_encrypted_and_file_mounted_secrets(tmp_path, monkeypatch):
    """Settings should transparently load *_FILE secrets and decrypt enc: values."""
    master_key = generate_fernet_key()
    enc_secret = encrypt_env_value("my-decrypted-openrouter-key", master_key=master_key)

    secret_file = tmp_path / "jwt_secret.txt"
    secret_file.write_text(generate_secret_key() + "\n", encoding="utf-8")

    monkeypatch.setenv("APP_MASTER_KEY", master_key)
    monkeypatch.setenv("SECRET_KEY_FILE", str(secret_file))

    cfg = Settings(
        ENVIRONMENT="production",
        USE_MOCK_AI=False,
        ENCRYPTION_KEY=generate_fernet_key(),
        OPENROUTER_API_KEY=enc_secret,
        POSTGRES_PASSWORD="StrongDbPassword!2026",
    )

    assert cfg.OPENROUTER_API_KEY == "my-decrypted-openrouter-key"
    assert cfg.SECRET_KEY == secret_file.read_text(encoding="utf-8").strip()

    summary = cfg.redacted_summary()
    assert summary["OPENROUTER_API_KEY"] != "my-decrypted-openrouter-key"
    assert summary["SECRET_KEY"] != cfg.SECRET_KEY
    assert summary["POSTGRES_PASSWORD"] != "StrongDbPassword!2026"


def test_settings_rejects_weak_or_default_production_secrets():
    """Production/staging settings must reject weak keys, default DB passwords, and invalid Fernet keys."""
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        Settings(ENCRYPTION_KEY="not-a-valid-fernet-key")

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            USE_MOCK_AI=True,
            SECRET_KEY="short_secret",
            ENCRYPTION_KEY=generate_fernet_key(),
            POSTGRES_PASSWORD="StrongPassword!123",
        )

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            USE_MOCK_AI=True,
            USE_SQLITE_LOCAL=False,
            DATABASE_URL=None,
            SECRET_KEY=generate_secret_key(),
            ENCRYPTION_KEY=generate_fernet_key(),
            POSTGRES_PASSWORD="postgres",
        )


def test_secret_redaction_filter_and_url_masking(monkeypatch):
    """SecretRedactionFilter scrubs URLs, Bearer tokens, and configured runtime secrets."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-abc123def456ghi789")
    assert (
        redact_url_credentials("postgresql://appuser:MySecretDbPass@db:5432/mealplanner")
        == "postgresql://appuser:****@db:5432/mealplanner"
    )
    assert mask_secret("abcdefghijkl") == "abcd...ijkl"
    assert sanitize_log_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig") == (
        "Authorization: Bearer ****"
    )

    log_filter = SecretRedactionFilter(extra_secrets=("CustomSecretValue123",))
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Failed connecting %s with %s",
        args=(
            "redis://:RedisPass99@localhost:6379/0",
            "sk-or-v1-abc123def456ghi789",
        ),
        exc_info=None,
    )
    assert log_filter.filter(record) is True
    assert "RedisPass99" not in str(record.args)
    assert "abc123def456ghi789" not in str(record.args)
