import os
import secrets
import time
import socket
import shutil
import base64
import qrcode
import threading
import tempfile
import subprocess
import argparse
import sys
from crypto import receive_packet , send_packet
from version import VERSION
# checks crypto file exits or not 
try:
    from crypto import derive_key, encrypt, decrypt
except ImportError:
    print("[-] Error: 'crypto.py' not found. Ensure encryption logic is available.")
    sys.exit(1)

def show_banner():
    """Display TorChat branded banner"""
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
║                    SERVER MODE (HOST)                        ║
║                                                              ║ 
╚══════════════════════════════════════════════════════════════╝     
                         v{VERSION}  

    🔒 ChaCha20-Poly1305 Encryption
    🧅 Tor Hidden Service  
    🎫 One-Time Invite URLs
    ⚡ Fast Bootstrap (~5s)

"""
    print(banner)


show_banner()
# added username feature
set_username = input("Enter your Host username: ").strip() or "Host"

parser = argparse.ArgumentParser(description='TorChat Server - Anonymous P2P Chat')
parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
parser.add_argument("--version", action="version", version=f"TorChat v{VERSION}")
args = parser.parse_args()

PASSWORD = "shared-secret"
KEY = derive_key(PASSWORD)
HOST = "127.0.0.1"
PORT = args.port


if shutil.which("tor") is None:
    print("[-] Error: 'tor' executable not found in PATH. Please install Tor.")
    sys.exit(1)

# EPHEMERAL tor for  When you start the server, it creates a temporary "hidden service." As soon as you stop the script, that .onion address is deleted forever. It cannot be reused or traced back to a specific session.

temp_dir = tempfile.mkdtemp(prefix="tor_chat_")
hs_dir = os.path.join(temp_dir, "hidden_service")

# tor requires strict 700 permissions on the HiddenServiceDir
os.makedirs(hs_dir, mode=0o700, exist_ok=True)

torrc_path = os.path.join(temp_dir, "torrc")
with open(torrc_path, "w") as f:
    f.write(f"DataDirectory {temp_dir}\n")
    f.write(f"HiddenServiceDir {hs_dir}\n")
    f.write(f"HiddenServicePort {PORT} 127.0.0.1:{PORT}\n")
    f.write("Log notice stdout\n")

print("[*] Launching isolated Tor instance...")
#
tor_proc = subprocess.Popen(
    ["tor", "-f", torrc_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

hostname_path = os.path.join(hs_dir, "hostname")
bootstrapped = False


print("[*] Waiting for Tor to descriptor circuit...")
start_time = time.time()
timeout = 120 # 2 min

while time.time() - start_time < timeout:
    # read tor output 
    line = tor_proc.stdout.readline()
    if line:
        if "Bootstrapped 100%" in line:
            print("[+] Tor network connection established.")
        if os.path.exists(hostname_path):
            bootstrapped = True
            break
    time.sleep(0.1)

if not bootstrapped:
    print("[-] Tor startup timeout or failure. Check your internet connection.")
    tor_proc.kill()
    shutil.rmtree(temp_dir)
    sys.exit(1)

with open(hostname_path) as f:
    onion_address = f.read().strip()

# one time invite
token_bytes = secrets.token_bytes(16)
invite_token = base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")
invite_expiry = int(time.time()) + 300
invite_url = f"chat://{onion_address}?token={invite_token}"

# updated as per client logic 
print("\n" + "="*50)
print("[+] ONION ADDRESS GENERATED")
print(f"Invite URL: {invite_url}")
print("\n IMPORTANT: Wait about 30 seconds before sending this link.")
print("The Tor network needs time to publish your address.")
print("="*50 + "\n")

try:
    qr = qrcode.QRCode()
    qr.add_data(invite_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
except Exception:
    print("[!] Could not generate QR code (check 'qrcode' library).")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((HOST, PORT))
except OSError:
    print(f"[!] Port {PORT} already in use. Close other instances.")
    tor_proc.kill()
    shutil.rmtree(temp_dir)
    sys.exit(1)

s.listen(1)
print(f"[+] Server listening on 127.0.0.1:{PORT}")
print("[+] Waiting for peer through Tor...")

conn, addr = s.accept()
print(f"[+] Peer Connected via Tor circuit")


# =================================================================
# previous logic 
# =================================================================
# def normalize_b64(token):
#     return base64.urlsafe_b64encode(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))).decode().rstrip("=")
#
# try:
#     token_msg = conn.recv(4096)
#     client_token = decrypt(KEY, token_msg).decode()
#     
#     if normalize_b64(client_token) != invite_token:
#         print("[-] Invalid token. Security breach attempt?")
#         conn.close()
#         sys.exit(1)
#
#     if int(time.time()) > invite_expiry:
#         print("[-] Invite expired.")
#         conn.close()
#         sys.exit(1)
#
#     print("[+] Identity Verified. Chat session encrypted.\n")
# except Exception as e:
#     print(f"[-] Validation failed: {e}")
#     conn.close()
#     sys.exit(1)
# =================================================================
# new logic as per crypto.py
# --- NEW v1.1.0 TOKEN & IDENTITY VALIDATION ---
try:
   
    packet = receive_packet(conn, KEY)
    
    if not packet or packet.get("type") != "auth":
        print("[-] Security break: Invalid handshake format.")
        conn.close()
        sys.exit(1)

    client_token = packet.get("content")
    peer_name = packet.get("user", "Peer")

    # Simple string comparison (Base64 is preserved in JSON strings)
    if client_token != invite_token:
        print(f"[-] Invalid token provided by {peer_name}. Denied.")
        conn.close()
        sys.exit(1)

    if int(time.time()) > invite_expiry:
        print("[-] Invite has expired.")
        conn.close()
        sys.exit(1)

    print(f"[+] Identity Verified. Peer: {peer_name}")
    print("[+] E2EE Active.\n")

except Exception as e:
    print(f"[-] Validation failed: {e}")
    conn.close()
    sys.exit(1)

# added full duplex 
'''def receive_loop():
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                print("\n[!] Peer disconnected.")
                break
            decrypted_msg = decrypt(KEY, data).decode()
            print(f"\rPeer: {decrypted_msg}\nYou: ", end="", flush=True)
        except Exception:
            break
'''
# new logic as per crypto.py
def receive_loop():
    while True:
        try:
            # receive_packet handles the decryption and decoding 
            packet = receive_packet(conn, KEY)
            if not packet:
                print("\n[!] Peer disconnected.")
                break
            
            sender = packet.get("user")
            content = packet.get("content")

            
            print(f"\r{sender}: {content}\nYou: ", end="", flush=True)
        except Exception:
            break
#
def send_loop():
    while True:
        try:
            msg = input("You: ")
            if msg.lower() in ['/quit', '/exit']:
                send_packet(conn, "status", set_username, "has left the chat.", KEY)
                break
            if msg:
                # it wraps your message in a JSON packet and send
                send_packet(conn, "msg", set_username, msg, KEY)
        except Exception:
            break
recv_thread = threading.Thread(target=receive_loop, daemon=True)
send_thread = threading.Thread(target=send_loop)
recv_thread.start()
send_thread.start()
send_thread.join()


print("\n[*] Shutting down and shredding ephemeral keys...")
try:
    conn.close()
    s.close()
    tor_proc.terminate()

    time.sleep(1) 
    shutil.rmtree(temp_dir, ignore_errors=True)
except Exception:
    pass
print("[*] Cleanup complete.")