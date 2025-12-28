import socket
import socks 
import base64
import threading
import sys
from urllib.parse import urlparse, parse_qs
from crypto import derive_key, encrypt, decrypt

def show_banner():
    """Display TorChat branded banner for client"""
    banner = """
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
║                        v1.0.0                                ║
╚══════════════════════════════════════════════════════════════╝

    🔗 Connecting via System Tor
    🎫 One-Time Invite Required
    🔒 ChaCha20-Poly1305 Decryption
    🧅 Anonymous Communication

"""
    print(banner)

def normalize_base64(token):
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode())
        return base64.urlsafe_b64encode(decoded).decode().rstrip("=")
    except Exception as e:
        print(f"[-] Invalid base64 token: {e}")
        sys.exit(1)


show_banner()

# invite
invite_url = input("Paste one-time invite: ").strip()
parsed = urlparse(invite_url)

onion_address = parsed.netloc.split('?')[0] if not parsed.hostname else parsed.hostname
token_list = parse_qs(parsed.query).get("token")

if not onion_address or not token_list:
    print("[-] Invalid invite URL. Make sure it looks like chat://[address].onion?token=...")
    sys.exit(1)

invite_token = token_list[0]
normalized_token = normalize_base64(invite_token)

# --- CONFIG ---
# this is your LOCAL Tor proxy. 
# use 9050 for system Tor, or 9150 if Tor browser open.

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9050 
ONION_PORT = 5000 

PASSWORD = "shared-secret"
KEY = derive_key(PASSWORD)


s = socks.socksocket()
try:
    print(f"[*] Routing through Tor proxy {PROXY_HOST}:{PROXY_PORT}...")
    s.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
    
    print(f"[*] Resolving and connecting to {onion_address}...")
    s.connect((onion_address, ONION_PORT))
    print("[+] Connected to peer over Tor circuit.")
except Exception as e:
    print(f"[-] Connection failed: {e}")
    print("[!] Is your local Tor service running? (sudo systemctl start tor)")
    sys.exit(1)

# invite token
try:
    s.send(encrypt(KEY, normalized_token.encode()))
except Exception as e:
    print(f"[-] Failed to send invite token: {e}")
    s.close()
    sys.exit(1)

# added full duplex 
def receive_loop():
    while True:
        try:
            data = s.recv(4096)
            if not data:
                print("\n[-] Connection closed by peer.")
                break
            msg = decrypt(KEY, data).decode()
            print(f"\rPeer: {msg}\nYou: ", end="", flush=True)
        except Exception:
            break

def send_loop():
    while True:
        try:
            msg = input("You: ")
            if msg:
                s.send(encrypt(KEY, msg.encode()))
        except Exception:
            break

print("[+] Validation sent. Waiting for chat to start...")
recv_thread = threading.Thread(target=receive_loop, daemon=True)
send_thread = threading.Thread(target=send_loop)
recv_thread.start()
send_thread.start()
send_thread.join()

s.close()