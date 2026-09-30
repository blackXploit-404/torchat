import json
import os
import struct
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

HEADER_SIZE = 4
MAX_PACKET_SIZE = 1024 * 1024


def derive_key(secret: str) -> bytes:
    return sha256(secret.encode()).digest()


def encrypt(key: bytes, message: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + ChaCha20Poly1305(key).encrypt(nonce, message, None)


def decrypt(key: bytes, data: bytes) -> bytes:
    return ChaCha20Poly1305(key).decrypt(data[:12], data[12:], None)


def send_packet(sock, packet_type: str, user: str, content, key: bytes) -> None:
    payload = json.dumps({"type": packet_type, "user": user, "content": content}).encode()
    frame = encrypt(key, payload)
    sock.sendall(struct.pack(">I", len(frame)) + frame)


def _read_exactly(sock, size: int):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_packet(sock, key: bytes):
    header = _read_exactly(sock, HEADER_SIZE)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    if length > MAX_PACKET_SIZE:
        raise ValueError("packet exceeds maximum size")
    frame = _read_exactly(sock, length)
    if frame is None:
        return None
    return json.loads(decrypt(key, frame))