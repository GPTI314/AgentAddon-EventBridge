"""
Core Cryptographic Service for SecretGateway

Implements secure cryptographic operations:
- Random secret generation
- Fernet symmetric encryption/decryption
- SHA-256 hashing with salt support
"""

import hashlib
import secrets
from typing import Optional, Tuple
from base64 import b64encode, b64decode

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoError(Exception):
    """Base exception for cryptographic operations"""
    pass


class EncryptionError(CryptoError):
    """Raised when encryption fails"""
    pass


class DecryptionError(CryptoError):
    """Raised when decryption fails"""
    pass


class CryptoService:
    """
    Cryptographic service providing secure operations for secret management.

    Features:
    - Cryptographically secure random secret generation
    - Fernet symmetric encryption (AES-128 in CBC mode with HMAC)
    - SHA-256 hashing with optional salt
    - Key derivation from passwords
    """

    DEFAULT_SECRET_LENGTH = 32  # 256 bits
    DEFAULT_SALT_LENGTH = 16    # 128 bits
    PBKDF2_ITERATIONS = 480000  # OWASP 2023 recommendation

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize CryptoService.

        Args:
            master_key: Optional pre-generated Fernet key (32 url-safe base64 bytes).
                       If not provided, a new key will be generated.
        """
        if master_key:
            try:
                self._fernet = Fernet(master_key)
                self._master_key = master_key
            except Exception as e:
                raise CryptoError(f"Invalid master key: {e}")
        else:
            self._master_key = Fernet.generate_key()
            self._fernet = Fernet(self._master_key)

    @property
    def master_key(self) -> bytes:
        """Get the current master encryption key"""
        return self._master_key

    def generate_secret(self, length: int = DEFAULT_SECRET_LENGTH) -> bytes:
        """
        Generate cryptographically secure random bytes.

        Uses secrets module which is suitable for managing sensitive data
        like authentication tokens, API keys, and secrets.

        Args:
            length: Number of random bytes to generate (default: 32)

        Returns:
            Random bytes of specified length

        Raises:
            ValueError: If length is not positive
        """
        if length <= 0:
            raise ValueError("Secret length must be positive")

        return secrets.token_bytes(length)

    def generate_secret_hex(self, length: int = DEFAULT_SECRET_LENGTH) -> str:
        """
        Generate cryptographically secure random hex string.

        Args:
            length: Number of random bytes to generate (default: 32)

        Returns:
            Hex string representation (2x length characters)
        """
        return secrets.token_hex(length)

    def generate_secret_urlsafe(self, length: int = DEFAULT_SECRET_LENGTH) -> str:
        """
        Generate cryptographically secure URL-safe random string.

        Args:
            length: Number of random bytes to generate (default: 32)

        Returns:
            URL-safe base64-encoded string
        """
        return secrets.token_urlsafe(length)

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypt data using Fernet symmetric encryption.

        Fernet guarantees that encrypted data cannot be manipulated or read
        without the key. It uses AES-128 in CBC mode with PKCS7 padding
        and HMAC for authentication.

        Args:
            plaintext: Data to encrypt

        Returns:
            Encrypted data (includes timestamp and HMAC)

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            return self._fernet.encrypt(plaintext)
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def encrypt_string(self, plaintext: str, encoding: str = "utf-8") -> bytes:
        """
        Encrypt a string using Fernet symmetric encryption.

        Args:
            plaintext: String to encrypt
            encoding: Text encoding (default: utf-8)

        Returns:
            Encrypted data

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            plaintext_bytes = plaintext.encode(encoding)
            return self.encrypt(plaintext_bytes)
        except UnicodeEncodeError as e:
            raise EncryptionError(f"Failed to encode plaintext: {e}")

    def decrypt(self, ciphertext: bytes, ttl: Optional[int] = None) -> bytes:
        """
        Decrypt data using Fernet symmetric encryption.

        Args:
            ciphertext: Encrypted data to decrypt
            ttl: Optional time-to-live in seconds. If provided, decryption
                 will fail if the token is older than ttl seconds.

        Returns:
            Decrypted plaintext

        Raises:
            DecryptionError: If decryption fails or token is invalid/expired
        """
        try:
            return self._fernet.decrypt(ciphertext, ttl=ttl)
        except InvalidToken:
            raise DecryptionError("Invalid or expired token")
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def decrypt_to_string(
        self,
        ciphertext: bytes,
        encoding: str = "utf-8",
        ttl: Optional[int] = None
    ) -> str:
        """
        Decrypt data and return as string.

        Args:
            ciphertext: Encrypted data to decrypt
            encoding: Text encoding (default: utf-8)
            ttl: Optional time-to-live in seconds

        Returns:
            Decrypted string

        Raises:
            DecryptionError: If decryption or decoding fails
        """
        plaintext_bytes = self.decrypt(ciphertext, ttl=ttl)
        try:
            return plaintext_bytes.decode(encoding)
        except UnicodeDecodeError as e:
            raise DecryptionError(f"Failed to decode decrypted data: {e}")

    def hash_data(
        self,
        data: bytes,
        salt: Optional[bytes] = None,
        return_salt: bool = False
    ) -> bytes | Tuple[bytes, bytes]:
        """
        Hash data using SHA-256 with optional salt.

        Args:
            data: Data to hash
            salt: Optional salt bytes. If not provided, will be generated.
            return_salt: If True, return tuple of (hash, salt)

        Returns:
            SHA-256 hash, or tuple of (hash, salt) if return_salt=True
        """
        if salt is None:
            salt = self.generate_secret(self.DEFAULT_SALT_LENGTH)

        hasher = hashlib.sha256()
        hasher.update(salt)
        hasher.update(data)
        hash_result = hasher.digest()

        if return_salt:
            return hash_result, salt
        return hash_result

    def hash_string(
        self,
        data: str,
        salt: Optional[bytes] = None,
        encoding: str = "utf-8",
        return_salt: bool = False
    ) -> bytes | Tuple[bytes, bytes]:
        """
        Hash a string using SHA-256 with optional salt.

        Args:
            data: String to hash
            salt: Optional salt bytes
            encoding: Text encoding (default: utf-8)
            return_salt: If True, return tuple of (hash, salt)

        Returns:
            SHA-256 hash, or tuple of (hash, salt) if return_salt=True
        """
        data_bytes = data.encode(encoding)
        return self.hash_data(data_bytes, salt=salt, return_salt=return_salt)

    def verify_hash(
        self,
        data: bytes,
        expected_hash: bytes,
        salt: bytes
    ) -> bool:
        """
        Verify that data matches expected hash with given salt.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            data: Data to verify
            expected_hash: Expected hash value
            salt: Salt used in original hash

        Returns:
            True if hash matches, False otherwise
        """
        computed_hash = self.hash_data(data, salt=salt)
        return secrets.compare_digest(computed_hash, expected_hash)

    def derive_key_from_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
        return_salt: bool = False
    ) -> bytes | Tuple[bytes, bytes]:
        """
        Derive an encryption key from a password using PBKDF2-HMAC-SHA256.

        Args:
            password: Password to derive key from
            salt: Optional salt. If not provided, will be generated.
            return_salt: If True, return tuple of (key, salt)

        Returns:
            32-byte encryption key suitable for Fernet, or tuple of (key, salt)
        """
        if salt is None:
            salt = self.generate_secret(self.DEFAULT_SALT_LENGTH)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )

        key = b64encode(kdf.derive(password.encode('utf-8')))

        if return_salt:
            return key, salt
        return key

    @staticmethod
    def generate_fernet_key() -> bytes:
        """
        Generate a new Fernet encryption key.

        Returns:
            32-byte URL-safe base64-encoded key suitable for Fernet
        """
        return Fernet.generate_key()

    @staticmethod
    def rotate_key(old_key: bytes, new_key: bytes, ciphertext: bytes) -> bytes:
        """
        Re-encrypt data with a new key (for key rotation).

        Args:
            old_key: Current encryption key
            new_key: New encryption key
            ciphertext: Data encrypted with old key

        Returns:
            Data re-encrypted with new key

        Raises:
            DecryptionError: If old key cannot decrypt data
            EncryptionError: If re-encryption fails
        """
        old_fernet = Fernet(old_key)
        new_fernet = Fernet(new_key)

        try:
            plaintext = old_fernet.decrypt(ciphertext)
        except InvalidToken:
            raise DecryptionError("Cannot decrypt with old key")
        except Exception as e:
            raise DecryptionError(f"Decryption with old key failed: {e}")

        try:
            return new_fernet.encrypt(plaintext)
        except Exception as e:
            raise EncryptionError(f"Re-encryption with new key failed: {e}")
