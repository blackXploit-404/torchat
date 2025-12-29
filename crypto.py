import os
import json # for username feature
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from hashlib import sha256


# Packet structure:
def send_packet(sock, p_type, user, content, key):
    """Wraps data in JSON, encrypts, and sends"""
    packet = {
        "type": p_type,
        "user": user,
        "content": content
    }
    encrypted_data = encrypt(key, json.dumps(packet).encode())
    sock.send(encrypted_data)

def receive_packet(sock, key):
    """Receives, decrypts, and converts JSON back to dict"""
    data = sock.recv(4096)
    if not data:
        return None
    decrypted_msg = decrypt(key, data).decode()
    return json.loads(decrypted_msg)


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
