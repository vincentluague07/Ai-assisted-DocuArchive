import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

class AES256Encryption:
    """AES-256 encryption service for sensitive data."""
    
    def __init__(self, key: bytes = None):
        if key is None:
            secret = os.environ.get('SESSION_SECRET', 'default-secret-key-32-chars-long')
            key = secret.encode('utf-8')[:32].ljust(32, b'\0')
        self.key = key
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using AES-256-CBC."""
        try:
            iv = os.urandom(16)
            
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
            
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            combined = iv + ciphertext
            return base64.b64encode(combined).decode('utf-8')
            
        except Exception as e:
            print(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data encrypted with AES-256-CBC."""
        try:
            combined = base64.b64decode(encrypted_data.encode('utf-8'))
            
            iv = combined[:16]
            ciphertext = combined[16:]
            
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            print(f"Decryption error: {e}")
            raise

encryption_service = AES256Encryption()

def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data using AES-256."""
    return encryption_service.encrypt(data)

def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return encryption_service.decrypt(encrypted_data)
