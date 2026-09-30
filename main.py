#!/usr/bin/env python3
import os
import socket
import subprocess
import sys

from version import VERSION

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
SERVER = os.path.join(BASE_DIR, "server.py")
CLIENT = os.path.join(BASE_DIR, "client.py")


def system_tor_available():
    try:
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect(("127.0.0.1", 9050))
        sock.close()
        return True
    except OSError:
        return False


def main():
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
║                    AppImage Edition                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
                         v{VERSION}
         🔒 Secure • 🧅 Anonymous • ⚡ Fast • 🎫 Ephemeral

    [1] Host room (Server)  - Create a group chat
    [2] Join room (Client)  - Connect to an existing room
"""
    )
    choice = input("Choose [1/2]: ").strip()

    if choice == "1":
        print("\n🚀 Starting room host (using embedded Tor)...")
        subprocess.run([PYTHON, SERVER], cwd=BASE_DIR)
        return

    if choice != "2":
        print("Invalid choice.")
        return

    print("\n🔗 Starting client mode...")
    if not system_tor_available():
        print("❌ System Tor not detected on port 9050")
        print("\n💡 Client mode requires system Tor.")
        print("   sudo systemctl start tor")
        print("   Or use Tor Browser (SOCKS on 9150)")
        sys.exit(1)

    print("✅ System Tor detected - proceeding with client...")
    subprocess.run([PYTHON, CLIENT], cwd=BASE_DIR)


if __name__ == "__main__":
    main()