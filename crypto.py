import os
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from hashlib import sha256

def derive_key(shared_password: str) -> bytes:
    return sha256(shared_password.encode()).digest()

def encrypt(key: bytes, message: bytes) -> bytes:
    nonce = os.urandom(12)
    cipher = ChaCha20Poly1305(key)
    return nonce + cipher.encrypt(nonce, message, None)

def decrypt(key: bytes, data: bytes) -> bytes:
    nonce = data[:12]
    ciphertext = data[12:]
    cipher = ChaCha20Poly1305(key)
    return cipher.decrypt(nonce, ciphertext, None)
