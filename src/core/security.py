import base64
import hashlib
from cryptography.fernet import Fernet
from src.core.config import settings
from src.core.exceptions import EncryptionError
from src.core.logger import logger

class EncryptionManager:
    """Manages symmetric encryption and decryption for sensitive configuration details."""
    
    def __init__(self) -> None:
        # Fernet requires a 32-byte base64 encoded key.
        if settings.ENCRYPTION_KEY:
            try:
                self.key = settings.ENCRYPTION_KEY.encode()
                self.cipher = Fernet(self.key)
            except Exception as e:
                logger.error(f"Invalid ENCRYPTION_KEY provided. Deriving fallback from SECRET_KEY. Error: {e}")
                self._derive_fallback_key()
        else:
            self._derive_fallback_key()

    def _derive_fallback_key(self) -> None:
        # Deterministically derive a secure key using SHA256 of the system's SECRET_KEY
        derived_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        self.key = base64.urlsafe_b64encode(derived_bytes)
        self.cipher = Fernet(self.key)

    def encrypt(self, plain_text: str) -> str:
        """Encrypts a string value. Returns base64 encoded ciphertext."""
        if not plain_text:
            return ""
        try:
            return self.cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {e}")

    def decrypt(self, cipher_text: str) -> str:
        """Decrypts a base64 encoded ciphertext value. Returns raw plaintext string."""
        if not cipher_text:
            return ""
        try:
            return self.cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {e}")

encryption_manager = EncryptionManager()
