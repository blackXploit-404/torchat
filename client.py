import socket
import socks 
import base64
import threading
import sys
import time
from urllib.parse import urlparse, parse_qs
from crypto import derive_key, encrypt, decrypt
from version import VERSION
from crypto import send_packet, receive_packet # added import for packet functions
def show_banner():
    """Display TorChat branded banner for client"""
    banner = f"""
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


# username added 
set_username = input("choose a cool username: ").strip() or "Anonymous"

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

# added better connection handling with retries
s = socks.socksocket()
s.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)

MAX_RETRIES = 12   # 12 tries * 10 seconds = 2 minutes total wait time
RETRY_DELAY = 10   # Seconds between attempts

connected = False

print(f"[*] Routing through Tor proxy {PROXY_HOST}:{PROXY_PORT}...")
print(f"[*] Target: {onion_address}")

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"[*] Connection attempt {attempt}/{MAX_RETRIES}...", end="\r")
        s.connect((onion_address, ONION_PORT))
        print(f"\n[+] Connected to peer over Tor circuit on attempt {attempt}!")
        connected = True
        break
    except Exception:
        if attempt < MAX_RETRIES:
            
            time.sleep(RETRY_DELAY)
        else:
            print(f"\n[-] Connection failed after {MAX_RETRIES} attempts.")
            print("[!] Possible reasons: Host is offline, Invite expired, or Tor is very slow today.")
            sys.exit(1)

if not connected:
    sys.exit(1)
# updated handshake with new packet format

# invite token
try:
    send_packet(s, "auth", set_username, normalized_token, KEY)
    #s.send(encrypt(KEY, normalized_token.encode()))
except Exception as e:
    print(f"[-] Failed to send invite token: {e}")
    s.close()
    sys.exit(1)

# added full duplex [ logic to handle JSON ]
def receive_loop():
    while True:
        try:
            packet = receive_packet(s, KEY)
            if packet is None:
                print("\n[-] Connection closed by peer.")
                break
           # extract from json packet 
            sender = packet.get("user", "Unknown")
            content = packet.get("content", "")
            p_type = packet.get("type", "msg")

            if p_type == "msg":
                print(f"\r{sender}: {content}\nYou: ", end="", flush=True)
            elif p_type == "status":
                # This is where 'typing' or 'joined' alerts appear
                print(f"\r[*] {sender} {content}", end="", flush=True)
                
        except Exception:
            break

def send_loop():
    while True:
        try:
            msg = input("You: ")
            if msg:
                if msg.lower() in ['/quit', '/exit']:
                    break
                # use new send packet fuct
                send_packet(s, "msg", set_username, msg, KEY)
        except Exception:
            break

print("[+] Validation sent. Waiting for chat to start...")
recv_thread = threading.Thread(target=receive_loop, daemon=True)
send_thread = threading.Thread(target=send_loop)
recv_thread.start()
send_thread.start()
send_thread.join()

s.close()