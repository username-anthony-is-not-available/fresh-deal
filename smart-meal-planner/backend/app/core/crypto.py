from cryptography.fernet import Fernet
from sqlalchemy import TypeDecorator, String
from app.core.config import settings

# Initialize Fernet with the encryption key from settings
fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_data(data: str) -> str:
    """Encrypts a string using AES (via Fernet)."""
    if data is None:
        return None
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(token: str) -> str:
    """Decrypts a Fernet token back to a string."""
    if token is None:
        return None
    return fernet.decrypt(token.encode()).decode()

class EncryptedString(TypeDecorator):
    """SQLAlchemy type for encrypting string data at rest."""
    impl = String

    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_data(str(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_data(value)
        return value

class EncryptedInt(TypeDecorator):
    """SQLAlchemy type for encrypting integer data at rest."""
    impl = String  # Store as encrypted string

    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_data(str(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            decrypted = decrypt_data(value)
            return int(decrypted) if decrypted is not None else None
        return value
