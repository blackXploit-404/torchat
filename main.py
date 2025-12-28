#!/usr/bin/env python3
import subprocess
import socket
import sys
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

SERVER = os.path.join(BASE_DIR, "server.py")
CLIENT = os.path.join(BASE_DIR, "client.py")

def check_system_tor():
    """Check if system Tor SOCKS proxy is available"""
    try:
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect(("127.0.0.1", 9050))
        sock.close()
        return True
    except Exception:
        return False

def show_main_banner():
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
║                   AppImage Edition v1.0.0                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

        🔒 Secure • 🧅 Anonymous • ⚡ Fast • 🎫 Ephemeral

    [1] Host chat (Server)  - Create new chat room
    [2] Connect to peer (Client) - Join existing chat
"""
    print(banner)

show_main_banner()
choice = input("Choose [1/2]: ").strip()

if choice == "1":
    print("\n🚀 Starting server mode (using embedded Tor)...")
    subprocess.run([PYTHON, SERVER], cwd=BASE_DIR)

elif choice == "2":
    print("\n🔗 Starting client mode...")

    if not check_system_tor():
        print("❌ System Tor not detected on port 9050")
        print("\n💡 Client mode requires system Tor.")
        print("   sudo systemctl start tor")
        print("   Or use Tor Browser (SOCKS on 9150)")
        sys.exit(1)

    print("✅ System Tor detected - proceeding with client...")
    subprocess.run([PYTHON, CLIENT], cwd=BASE_DIR)

else:
    print("❌ Invalid choice.")
