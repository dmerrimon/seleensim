"""
PII Encryption Module for SOC 2 Compliance

Provides symmetric encryption for Personally Identifiable Information (PII)
stored in the database, such as email addresses and display names.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).

Environment variable required:
    PII_ENCRYPTION_KEY - Base64-encoded 32-byte key
    Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class PIIEncryptionError(Exception):
    """Raised when PII encryption/decryption fails"""
    pass


class PIIEncryption:
    """
    Handles encryption and decryption of PII data.

    Uses Fernet symmetric encryption which provides:
    - AES-128 encryption in CBC mode
    - HMAC-SHA256 authentication
    - Automatic key derivation from password

    All encrypted values are URL-safe base64 encoded strings.
    """

    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryption with the provided key.

        Args:
            key: Base64-encoded Fernet key. If not provided,
                 reads from PII_ENCRYPTION_KEY environment variable.
        """
        self._fernet = None
        self._key = key or os.getenv("PII_ENCRYPTION_KEY")

        if self._key:
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(self._key.encode())
                logger.info("✅ PII encryption initialized")
            except Exception as e:
                logger.warning(f"⚠️ PII encryption initialization failed: {e}")
                self._fernet = None
        else:
            logger.warning("⚠️ PII_ENCRYPTION_KEY not set - encryption disabled")

    @property
    def is_enabled(self) -> bool:
        """Check if encryption is enabled and properly configured"""
        return self._fernet is not None

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string, or original if encryption disabled

        Raises:
            PIIEncryptionError: If encryption fails
        """
        if plaintext is None:
            return None

        if not self.is_enabled:
            # Return plaintext if encryption is not configured
            # This allows gradual rollout
            return plaintext

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"PII encryption failed: {e}")
            raise PIIEncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string to decrypt

        Returns:
            Decrypted plaintext string

        Raises:
            PIIEncryptionError: If decryption fails
        """
        if ciphertext is None:
            return None

        if not self.is_enabled:
            # Return as-is if encryption is not configured
            # This handles unencrypted legacy data
            return ciphertext

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            # Check if this might be unencrypted legacy data
            # Fernet tokens always start with 'gAAAAA'
            if not ciphertext.startswith('gAAAAA'):
                logger.debug("Data appears to be unencrypted (legacy)")
                return ciphertext

            logger.error(f"PII decryption failed: {e}")
            raise PIIEncryptionError(f"Decryption failed: {e}")

    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing data to encrypt
            fields: List of field names to encrypt

        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(result[field])
        return result

    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing encrypted data
            fields: List of field names to decrypt

        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(result[field])
                except PIIEncryptionError:
                    # Keep original value if decryption fails
                    # (handles mixed encrypted/unencrypted data during migration)
                    pass
        return result


# Global singleton instance
@lru_cache(maxsize=1)
def get_pii_encryptor() -> PIIEncryption:
    """Get or create the global PII encryptor instance"""
    return PIIEncryption()


# Convenience functions
def encrypt_pii(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a PII value"""
    return get_pii_encryptor().encrypt(plaintext)


def decrypt_pii(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a PII value"""
    return get_pii_encryptor().decrypt(ciphertext)


def is_encryption_enabled() -> bool:
    """Check if PII encryption is enabled"""
    return get_pii_encryptor().is_enabled


# Fields that should be encrypted
PII_FIELDS = ["email", "display_name"]


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded key string for use as PII_ENCRYPTION_KEY

    Usage:
        python -c "from utils.encryption import generate_encryption_key; print(generate_encryption_key())"
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # Generate a new key when run directly
    print("Generated PII_ENCRYPTION_KEY:")
    print(generate_encryption_key())
    print("\nAdd this to your environment variables.")
