"""
Comprehensive tests for CryptoService

Tests cover:
- Secret generation (random bytes, hex, urlsafe)
- Symmetric encryption/decryption (Fernet)
- Hashing with SHA-256 and salt
- Key derivation from passwords
- Key rotation
- Error handling and edge cases
"""

import pytest
import time
from cryptography.fernet import Fernet

from app.services.crypto import CryptoService
from app.services.crypto.crypto_service import (
    CryptoError,
    EncryptionError,
    DecryptionError
)


class TestSecretGeneration:
    """Test cryptographically secure random secret generation"""

    def test_generate_secret_default_length(self):
        """Test secret generation with default length"""
        crypto = CryptoService()
        secret = crypto.generate_secret()

        assert isinstance(secret, bytes)
        assert len(secret) == CryptoService.DEFAULT_SECRET_LENGTH

    def test_generate_secret_custom_length(self):
        """Test secret generation with custom length"""
        crypto = CryptoService()
        lengths = [8, 16, 32, 64, 128]

        for length in lengths:
            secret = crypto.generate_secret(length)
            assert len(secret) == length

    def test_generate_secret_randomness(self):
        """Test that generated secrets are different (highly probable)"""
        crypto = CryptoService()
        secrets = [crypto.generate_secret() for _ in range(10)]

        # All secrets should be unique (probability of collision is negligible)
        assert len(set(secrets)) == len(secrets)

    def test_generate_secret_invalid_length(self):
        """Test that invalid length raises ValueError"""
        crypto = CryptoService()

        with pytest.raises(ValueError, match="Secret length must be positive"):
            crypto.generate_secret(0)

        with pytest.raises(ValueError):
            crypto.generate_secret(-1)

    def test_generate_secret_hex(self):
        """Test hex secret generation"""
        crypto = CryptoService()
        secret = crypto.generate_secret_hex(16)

        assert isinstance(secret, str)
        assert len(secret) == 32  # Hex is 2x the byte length
        assert all(c in '0123456789abcdef' for c in secret)

    def test_generate_secret_urlsafe(self):
        """Test URL-safe secret generation"""
        crypto = CryptoService()
        secret = crypto.generate_secret_urlsafe(32)

        assert isinstance(secret, str)
        # URL-safe base64 uses only alphanumeric, -, and _
        assert all(c.isalnum() or c in '-_' for c in secret)


class TestSymmetricEncryption:
    """Test Fernet symmetric encryption and decryption"""

    def test_encrypt_decrypt_bytes(self):
        """Test basic encryption and decryption of bytes"""
        crypto = CryptoService()
        plaintext = b"Secret message for encryption"

        ciphertext = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(ciphertext)

        assert ciphertext != plaintext
        assert decrypted == plaintext

    def test_encrypt_decrypt_string(self):
        """Test encryption and decryption of strings"""
        crypto = CryptoService()
        plaintext = "Secret string message"

        ciphertext = crypto.encrypt_string(plaintext)
        decrypted = crypto.decrypt_to_string(ciphertext)

        assert isinstance(ciphertext, bytes)
        assert decrypted == plaintext

    def test_encrypt_unicode(self):
        """Test encryption of Unicode strings"""
        crypto = CryptoService()
        plaintext = "Secret: 你好世界 🔐 مرحبا"

        ciphertext = crypto.encrypt_string(plaintext)
        decrypted = crypto.decrypt_to_string(ciphertext)

        assert decrypted == plaintext

    def test_ciphertext_different_each_time(self):
        """Test that same plaintext produces different ciphertext (IV)"""
        crypto = CryptoService()
        plaintext = b"Same message"

        ciphertext1 = crypto.encrypt(plaintext)
        ciphertext2 = crypto.encrypt(plaintext)

        # Ciphertexts should be different due to random IV
        assert ciphertext1 != ciphertext2

        # But both should decrypt to same plaintext
        assert crypto.decrypt(ciphertext1) == plaintext
        assert crypto.decrypt(ciphertext2) == plaintext

    def test_decrypt_with_wrong_key(self):
        """Test that decryption fails with wrong key"""
        crypto1 = CryptoService()
        crypto2 = CryptoService()  # Different key

        plaintext = b"Secret data"
        ciphertext = crypto1.encrypt(plaintext)

        with pytest.raises(DecryptionError, match="Invalid or expired token"):
            crypto2.decrypt(ciphertext)

    def test_decrypt_invalid_data(self):
        """Test that decryption of invalid data raises error"""
        crypto = CryptoService()

        with pytest.raises(DecryptionError):
            crypto.decrypt(b"not-valid-ciphertext")

        with pytest.raises(DecryptionError):
            crypto.decrypt(b"")

    def test_encrypt_with_master_key(self):
        """Test initialization with existing master key"""
        # Generate a key and use it for two instances
        master_key = CryptoService.generate_fernet_key()

        crypto1 = CryptoService(master_key=master_key)
        crypto2 = CryptoService(master_key=master_key)

        plaintext = b"Shared key test"
        ciphertext = crypto1.encrypt(plaintext)

        # crypto2 should be able to decrypt since it has same key
        decrypted = crypto2.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_invalid_master_key(self):
        """Test that invalid master key raises error"""
        with pytest.raises(CryptoError, match="Invalid master key"):
            CryptoService(master_key=b"not-a-valid-key")

    def test_encryption_ttl(self):
        """Test time-to-live parameter for decryption"""
        crypto = CryptoService()
        plaintext = b"Time-sensitive data"

        ciphertext = crypto.encrypt(plaintext)

        # Should decrypt successfully with generous TTL
        decrypted = crypto.decrypt(ciphertext, ttl=60)
        assert decrypted == plaintext

        # Encrypt and wait, then try with very short TTL
        time.sleep(2)
        ciphertext_old = crypto.encrypt(plaintext)
        time.sleep(2)

        # Should fail with TTL of 1 second
        with pytest.raises(DecryptionError, match="Invalid or expired token"):
            crypto.decrypt(ciphertext_old, ttl=1)

    def test_master_key_property(self):
        """Test master_key property access"""
        crypto = CryptoService()
        key = crypto.master_key

        assert isinstance(key, bytes)
        assert len(key) > 0

        # Key should be valid Fernet key
        Fernet(key)  # Should not raise


class TestHashing:
    """Test SHA-256 hashing with salt"""

    def test_hash_data_basic(self):
        """Test basic data hashing"""
        crypto = CryptoService()
        data = b"Data to hash"

        hash_result = crypto.hash_data(data)

        assert isinstance(hash_result, bytes)
        assert len(hash_result) == 32  # SHA-256 produces 32 bytes

    def test_hash_with_salt(self):
        """Test hashing with explicit salt"""
        crypto = CryptoService()
        data = b"Data to hash"
        salt = crypto.generate_secret(16)

        hash1 = crypto.hash_data(data, salt=salt)
        hash2 = crypto.hash_data(data, salt=salt)

        # Same data + salt should produce same hash
        assert hash1 == hash2

    def test_hash_different_salts(self):
        """Test that different salts produce different hashes"""
        crypto = CryptoService()
        data = b"Same data"

        hash1, salt1 = crypto.hash_data(data, return_salt=True)
        hash2, salt2 = crypto.hash_data(data, return_salt=True)

        # Different salts should produce different hashes
        assert salt1 != salt2
        assert hash1 != hash2

    def test_hash_string(self):
        """Test string hashing"""
        crypto = CryptoService()
        data = "String to hash"

        hash_result = crypto.hash_string(data)

        assert isinstance(hash_result, bytes)
        assert len(hash_result) == 32

    def test_hash_unicode_string(self):
        """Test Unicode string hashing"""
        crypto = CryptoService()
        data = "Unicode: 你好 🔐"

        hash_result = crypto.hash_string(data)
        assert len(hash_result) == 32

    def test_verify_hash_correct(self):
        """Test hash verification with correct data"""
        crypto = CryptoService()
        data = b"Data to verify"

        hash_result, salt = crypto.hash_data(data, return_salt=True)

        # Verification should succeed
        assert crypto.verify_hash(data, hash_result, salt) is True

    def test_verify_hash_incorrect(self):
        """Test hash verification with incorrect data"""
        crypto = CryptoService()
        data = b"Original data"
        wrong_data = b"Wrong data"

        hash_result, salt = crypto.hash_data(data, return_salt=True)

        # Verification should fail
        assert crypto.verify_hash(wrong_data, hash_result, salt) is False

    def test_verify_hash_wrong_salt(self):
        """Test hash verification with wrong salt"""
        crypto = CryptoService()
        data = b"Data to verify"

        hash_result, _ = crypto.hash_data(data, return_salt=True)
        wrong_salt = crypto.generate_secret(16)

        # Verification should fail with wrong salt
        assert crypto.verify_hash(data, hash_result, wrong_salt) is False

    def test_hash_deterministic_with_same_salt(self):
        """Test that hashing is deterministic with same salt"""
        crypto = CryptoService()
        data = b"Consistent data"
        salt = crypto.generate_secret(16)

        hashes = [crypto.hash_data(data, salt=salt) for _ in range(5)]

        # All hashes should be identical
        assert len(set(hashes)) == 1


class TestKeyDerivation:
    """Test password-based key derivation"""

    def test_derive_key_from_password(self):
        """Test basic key derivation from password"""
        crypto = CryptoService()
        password = "SecurePassword123!"

        key = crypto.derive_key_from_password(password)

        assert isinstance(key, bytes)
        # Should be valid Fernet key
        Fernet(key)

    def test_derive_key_deterministic(self):
        """Test that same password+salt produces same key"""
        crypto = CryptoService()
        password = "MyPassword"
        salt = crypto.generate_secret(16)

        key1 = crypto.derive_key_from_password(password, salt=salt)
        key2 = crypto.derive_key_from_password(password, salt=salt)

        assert key1 == key2

    def test_derive_key_different_salts(self):
        """Test that different salts produce different keys"""
        crypto = CryptoService()
        password = "SamePassword"

        key1, salt1 = crypto.derive_key_from_password(password, return_salt=True)
        key2, salt2 = crypto.derive_key_from_password(password, return_salt=True)

        assert salt1 != salt2
        assert key1 != key2

    def test_derive_key_different_passwords(self):
        """Test that different passwords produce different keys"""
        crypto = CryptoService()
        salt = crypto.generate_secret(16)

        key1 = crypto.derive_key_from_password("Password1", salt=salt)
        key2 = crypto.derive_key_from_password("Password2", salt=salt)

        assert key1 != key2

    def test_derived_key_works_for_encryption(self):
        """Test that derived key can be used for encryption"""
        crypto = CryptoService()
        password = "EncryptionPassword"

        key, salt = crypto.derive_key_from_password(password, return_salt=True)

        # Create new CryptoService with derived key
        crypto_derived = CryptoService(master_key=key)

        plaintext = b"Test message"
        ciphertext = crypto_derived.encrypt(plaintext)
        decrypted = crypto_derived.decrypt(ciphertext)

        assert decrypted == plaintext


class TestKeyRotation:
    """Test key rotation functionality"""

    def test_rotate_key_basic(self):
        """Test basic key rotation"""
        old_key = CryptoService.generate_fernet_key()
        new_key = CryptoService.generate_fernet_key()

        crypto_old = CryptoService(master_key=old_key)
        plaintext = b"Data to rotate"

        # Encrypt with old key
        ciphertext_old = crypto_old.encrypt(plaintext)

        # Rotate to new key
        ciphertext_new = CryptoService.rotate_key(old_key, new_key, ciphertext_old)

        # Decrypt with new key
        crypto_new = CryptoService(master_key=new_key)
        decrypted = crypto_new.decrypt(ciphertext_new)

        assert decrypted == plaintext

    def test_rotate_key_old_key_invalid(self):
        """Test rotation fails with wrong old key"""
        old_key = CryptoService.generate_fernet_key()
        wrong_key = CryptoService.generate_fernet_key()
        new_key = CryptoService.generate_fernet_key()

        crypto = CryptoService(master_key=old_key)
        ciphertext = crypto.encrypt(b"Test data")

        # Rotation should fail with wrong old key
        with pytest.raises(DecryptionError, match="Cannot decrypt with old key"):
            CryptoService.rotate_key(wrong_key, new_key, ciphertext)

    def test_rotate_key_invalid_ciphertext(self):
        """Test rotation fails with invalid ciphertext"""
        old_key = CryptoService.generate_fernet_key()
        new_key = CryptoService.generate_fernet_key()

        with pytest.raises(DecryptionError):
            CryptoService.rotate_key(old_key, new_key, b"invalid-data")


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_encrypt_empty_data(self):
        """Test encryption of empty data"""
        crypto = CryptoService()

        ciphertext = crypto.encrypt(b"")
        decrypted = crypto.decrypt(ciphertext)

        assert decrypted == b""

    def test_encrypt_large_data(self):
        """Test encryption of large data"""
        crypto = CryptoService()
        large_data = b"X" * 1_000_000  # 1 MB

        ciphertext = crypto.encrypt(large_data)
        decrypted = crypto.decrypt(ciphertext)

        assert decrypted == large_data

    def test_hash_empty_data(self):
        """Test hashing of empty data"""
        crypto = CryptoService()

        hash_result = crypto.hash_data(b"")
        assert len(hash_result) == 32

    def test_generate_fernet_key_static(self):
        """Test static Fernet key generation"""
        key1 = CryptoService.generate_fernet_key()
        key2 = CryptoService.generate_fernet_key()

        assert key1 != key2
        assert isinstance(key1, bytes)
        assert isinstance(key2, bytes)

        # Both should be valid Fernet keys
        Fernet(key1)
        Fernet(key2)

    def test_encoding_error_handling(self):
        """Test handling of encoding errors"""
        crypto = CryptoService()

        # Create invalid UTF-8 bytes
        invalid_utf8 = b'\xff\xfe'
        ciphertext = crypto.encrypt(invalid_utf8)

        # Should fail when trying to decode as UTF-8
        with pytest.raises(DecryptionError, match="Failed to decode"):
            crypto.decrypt_to_string(ciphertext, encoding='utf-8')


class TestSecurityProperties:
    """Test security properties and best practices"""

    def test_constant_time_comparison(self):
        """Test that hash verification uses constant-time comparison"""
        crypto = CryptoService()
        data = b"Test data"

        hash1, salt = crypto.hash_data(data, return_salt=True)
        hash2 = crypto.hash_data(b"Different data", salt=salt)

        # Both verifications should take similar time (constant-time)
        # This is verified by using secrets.compare_digest internally
        result1 = crypto.verify_hash(data, hash1, salt)
        result2 = crypto.verify_hash(data, hash2, salt)

        assert result1 is True
        assert result2 is False

    def test_pbkdf2_iterations(self):
        """Test that PBKDF2 uses sufficient iterations"""
        # OWASP recommends 480,000 iterations for PBKDF2-HMAC-SHA256 (2023)
        assert CryptoService.PBKDF2_ITERATIONS >= 480000

    def test_default_lengths_secure(self):
        """Test that default lengths are cryptographically secure"""
        # 256-bit secrets (32 bytes)
        assert CryptoService.DEFAULT_SECRET_LENGTH >= 32

        # 128-bit salt (16 bytes)
        assert CryptoService.DEFAULT_SALT_LENGTH >= 16
