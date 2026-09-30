import argparse
import base64
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import qrcode

from crypto import derive_key, receive_packet, send_packet
from version import VERSION

HOST = "127.0.0.1"
MAX_PEERS = 16
HANDSHAKE_TIMEOUT = 60
BOOTSTRAP_TIMEOUT = 120


class Peer:
    def __init__(self, conn, name):
        self.conn = conn
        self.name = name
        self.lock = threading.Lock()


class Room:
    def __init__(self, key):
        self.key = key
        self.peers = {}
        self.lock = threading.Lock()

    def join(self, conn, name):
        with self.lock:
            if len(self.peers) >= MAX_PEERS:
                return None
            taken = {peer.name for peer in self.peers.values()}
            unique = name
            suffix = 2
            while unique in taken:
                unique = f"{name}-{suffix}"
                suffix += 1
            peer = Peer(conn, unique)
            self.peers[conn] = peer
            return peer

    def leave(self, conn):
        with self.lock:
            return self.peers.pop(conn, None)

    def names(self):
        with self.lock:
            return [peer.name for peer in self.peers.values()]

    def broadcast(self, packet_type, user, content, exclude=None):
        with self.lock:
            targets = list(self.peers.items())
        for conn, peer in targets:
            if conn is exclude:
                continue
            try:
                with peer.lock:
                    send_packet(conn, packet_type, user, content, self.key)
            except OSError:
                self.leave(conn)

    def serve(self, conn):
        try:
            conn.settimeout(HANDSHAKE_TIMEOUT)
            packet = receive_packet(conn, self.key)
            if packet is None or packet.get("type") != "auth":
                return
            peer = self.join(conn, str(packet.get("user", "")).strip() or "Anonymous")
            if peer is None:
                send_packet(conn, "status", "Host", "Room is full.", self.key)
                return
            self.broadcast("status", "Host", f"{peer.name} joined the room.")
            print(f"\r\033[2K[+] {peer.name} joined. Online: {', '.join(self.names())}\nYou: ", end="", flush=True)
            while True:
                conn.settimeout(None)
                packet = receive_packet(conn, self.key)
                if packet is None:
                    break
                message = packet.get("content", "")
                self.broadcast(
                    packet.get("type", "msg"),
                    peer.name,
                    message,
                    exclude=conn,
                )
                if packet.get("type") != "status":
                    print(f"\r\033[2K[{peer.name}] {message}\nYou: ", end="", flush=True)
        except Exception:
            pass
        finally:
            peer = self.leave(conn)
            conn.close()
            if peer is not None:
                self.broadcast("status", "Host", f"{peer.name} left the room.")
                print(f"\r\033[2K[-] {peer.name} left. Online: {', '.join(self.names())}\nYou: ", end="", flush=True)

    def accept_forever(self, listener):
        while True:
            conn, _ = listener.accept()
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()


def show_banner():
    print(
        f"""
╔══════════════════════════════════════════════════════════════╗
║  ████████╗ ██████╗ ██████╗  ██████╗██╗  ██╗ █████╗ ████████╗ ║
║  ╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝██║  ██║██╔══██╗╚══██╔══╝ ║
║     ██║   ██║   ██║██████╔╝██║     ███████║███████║   ██║    ║
║     ██║   ██║   ██║██╔══██╗██║     ██╔══██║██╔══██║   ██║    ║
║     ██║   ╚██████╔╝██║  ██║╚██████╗██║  ██║██║  ██║   ██║    ║
║     ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ║
║                                                              ║
║           Anonymous P2P Chat over Tor Network                ║
║              End-to-End Encrypted • Ephemeral                ║
║                                                              ║
║                   SERVER MODE (ROOM HOST)                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
                         v{VERSION}

    🔒 ChaCha20-Poly1305 Encryption
    🧅 Tor Hidden Service
    🎫 Invite Links (up to {MAX_PEERS} peers)
    ⚡ Fast Bootstrap (~5s)

    Commands: /list  /invite  /quit
"""
    )


def start_tor(port):
    if shutil.which("tor") is None:
        print("[-] Error: 'tor' executable not found in PATH. Please install Tor.")
        sys.exit(1)

    data_dir = tempfile.mkdtemp(prefix="tor_chat_")
    service_dir = os.path.join(data_dir, "hidden_service")
    os.makedirs(service_dir, mode=0o700, exist_ok=True)
    torrc_path = os.path.join(data_dir, "torrc")
    with open(torrc_path, "w") as f:
        f.write(f"DataDirectory {data_dir}\n")
        f.write(f"HiddenServiceDir {service_dir}\n")
        f.write(f"HiddenServicePort {port} 127.0.0.1:{port}\n")
        f.write("Log notice stdout\n")

    print("[*] Launching isolated Tor instance...")
    process = subprocess.Popen(
        ["tor", "-f", torrc_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    hostname_path = os.path.join(service_dir, "hostname")
    deadline = time.time() + BOOTSTRAP_TIMEOUT
    while time.time() < deadline:
        line = process.stdout.readline()
        if line and "Bootstrapped 100%" in line:
            print("[+] Tor network connection established.")
        if os.path.exists(hostname_path):
            with open(hostname_path) as f:
                return process, data_dir, f.read().strip()

    process.kill()
    shutil.rmtree(data_dir, ignore_errors=True)
    print("[-] Tor startup timeout or failure. Check your internet connection.")
    sys.exit(1)


def print_invite(invite_url):
    print("\n" + "=" * 50)
    print("[+] ONION ADDRESS GENERATED")
    print(f"Invite link: {invite_url}")
    print(f"Room capacity: {MAX_PEERS} peers")
    print("\n IMPORTANT: Wait about 30 seconds before sharing this link.")
    print("The Tor network needs time to publish your address.")
    print("=" * 50 + "\n")
    try:
        qr = qrcode.QRCode()
        qr.add_data(invite_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("[!] Could not generate QR code (check 'qrcode' library).")


def host_commands(room, invite_url, host_name):
    while True:
        try:
            message = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not message:
            continue
        if message.lower() in ("/quit", "/exit"):
            room.broadcast("status", host_name, "closed the room.")
            return
        if message == "/list":
            online = room.names() + [host_name]
            print(f"\nOnline: {', '.join(online)}\nYou: ", end="", flush=True)
            continue
        if message == "/invite":
            print(f"\nInvite link: {invite_url}\nYou: ", end="", flush=True)
            continue
        room.broadcast("msg", host_name, message)


def run():
    show_banner()

    host_name = input("Enter your display name: ").strip() or "Host"

    parser = argparse.ArgumentParser(description="TorChat Server - Anonymous group chat")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    parser.add_argument("--version", action="version", version=f"TorChat v{VERSION}")
    args = parser.parse_args()

    room_secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    room = Room(derive_key(room_secret))

    tor_process, data_dir, onion_address = start_tor(args.port)
    invite_url = f"chat://{onion_address}?key={room_secret}"
    print_invite(invite_url)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((HOST, args.port))
    except OSError:
        print(f"[!] Port {args.port} already in use. Close other instances.")
        tor_process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)
        sys.exit(1)
    listener.listen(MAX_PEERS)
    print(f"[+] Room open on {HOST}:{args.port}")

    threading.Thread(target=room.accept_forever, args=(listener,), daemon=True).start()

    host_commands(room, invite_url, host_name)

    listener.close()
    tor_process.terminate()
    time.sleep(1)
    shutil.rmtree(data_dir, ignore_errors=True)
    print("\n[*] Room closed and ephemeral keys shredded.")


if __name__ == "__main__":
    run()