import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

import socks

from crypto import derive_key, receive_packet, send_packet
from version import VERSION

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9050
ONION_PORT = 5000
MAX_RETRIES = 12
RETRY_DELAY = 10
SOCKET_TIMEOUT = 60


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
║                   CLIENT MODE (JOIN)                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
                         v{VERSION}

    🔗 Connecting via System Tor
    🔒 ChaCha20-Poly1305 Decryption
    🧅 Anonymous Communication

    Commands: /quit
"""
    )


def parse_invite(invite_url):
    parsed = urlparse(invite_url.strip())
    room_secret = parse_qs(parsed.query).get("key", [None])[0]
    if not parsed.hostname or not room_secret:
        print("[-] Invalid invite link. Expected chat://[address].onion?key=...")
        sys.exit(1)
    return parsed.hostname, room_secret


def connect(onion_address):
    sock = socks.socksocket()
    sock.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
    sock.settimeout(SOCKET_TIMEOUT)
    print(f"[*] Routing through Tor proxy {PROXY_HOST}:{PROXY_PORT}...")
    print(f"[*] Target: {onion_address}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[*] Connection attempt {attempt}/{MAX_RETRIES}...", end="\r")
            sock.connect((onion_address, ONION_PORT))
            print(f"\n[+] Connected to room over Tor circuit on attempt {attempt}!")
            return sock
        except Exception:
            if attempt == MAX_RETRIES:
                print(f"\n[-] Connection failed after {MAX_RETRIES} attempts.")
                print("[!] Host may be offline, or Tor is very slow today.")
                sys.exit(1)
            time.sleep(RETRY_DELAY)


def receive_loop(sock, key):
    while True:
        try:
            packet = receive_packet(sock, key)
            if packet is None:
                print("\n[-] Host closed the room.")
                return
            user = packet.get("user", "Unknown")
            if packet.get("type") == "status":
                line = f"[*] {user}: {packet.get('content', '')}"
            else:
                line = f"[{user}] {packet.get('content', '')}"
            print(f"\r\033[2K{line}\nYou: ", end="", flush=True)
        except Exception:
            print("\n[-] Connection lost.")
            return


def send_loop(sock, key, user_name):
    while True:
        try:
            message = input("You: ").strip()
            if not message:
                continue
            if message.lower() in ("/quit", "/exit"):
                return
            send_packet(sock, "msg", user_name, message, key)
        except Exception:
            return


def run():
    show_banner()

    user_name = input("Choose a display name: ").strip() or "Anonymous"
    onion_address, room_secret = parse_invite(input("Paste invite link: "))
    key = derive_key(room_secret)

    sock = connect(onion_address)
    try:
        send_packet(sock, "auth", user_name, "", key)
    except Exception as error:
        print(f"[-] Could not join room: {error}")
        sock.close()
        sys.exit(1)

    print("[+] Joined room. Type a message and press enter.\n")
    threading.Thread(target=receive_loop, args=(sock, key), daemon=True).start()
    send_loop(sock, key, user_name)
    sock.close()
    print("[*] Left the room.")


if __name__ == "__main__":
    run()