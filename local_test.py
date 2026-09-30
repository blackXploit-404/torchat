import socket
import threading
import time

from crypto import derive_key, receive_packet, send_packet
from server import MAX_PEERS, Room

KEY = derive_key("local-test-secret")
ROOM_KEY = "local-test-secret"
RECV_WINDOW = 1.5


class LocalRoom(Room):
    def __init__(self, key):
        super().__init__(key)
        self.log = []

    def accept_forever(self, listener):
        while True:
            conn, _ = listener.accept()
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()


def start_room():
    room = LocalRoom(KEY)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(MAX_PEERS)
    threading.Thread(target=room.accept_forever, args=(listener,), daemon=True).start()
    return room, listener.getsockname()[1]


def join(port, name):
    conn = socket.socket()
    conn.connect(("127.0.0.1", port))
    send_packet(conn, "auth", name, "", KEY)
    return conn


def read_all(conn, window=RECV_WINDOW):
    received = []
    conn.settimeout(0.2)
    deadline = time.time() + window
    while time.time() < deadline:
        try:
            packet = receive_packet(conn, KEY)
        except socket.timeout:
            continue
        except Exception:
            break
        if packet is None:
            break
        received.append(packet)
    return received


def texts(packets):
    return [f"{p.get('user')}: {p.get('content')}" for p in packets]


def spam(conn, name, count):
    for index in range(count):
        send_packet(conn, "msg", name, f"{name}-{index}", KEY)


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}{f'  -> {detail}' if detail else ''}")
    return condition


def main():
    room, port = start_room()
    print(f"local room on 127.0.0.1:{port}\n")
    results = []

    alice = join(port, "alice")
    bob = join(port, "bob")
    carol = join(port, "carol")
    time.sleep(0.4)
    read_all(alice)
    read_all(bob)
    read_all(carol)

    send_packet(bob, "msg", "bob", "hello everyone", KEY)
    time.sleep(0.3)
    alice_packets = read_all(alice)
    bob_packets = read_all(bob)
    carol_packets = read_all(carol)
    results.append(check("1. message relays to other peers", texts(alice_packets) == ["bob: hello everyone"], texts(alice_packets)))
    results.append(check("2. message reaches last peer in room", texts(carol_packets) == ["bob: hello everyone"], texts(carol_packets)))
    results.append(check("3. sender does not receive own message", bob_packets == [], texts(bob_packets)))

    duplicate = join(port, "bob")
    time.sleep(0.4)
    results.append(check("4. duplicate name gets a suffix", "bob-2" in room.names(), ", ".join(room.names())))
    read_all(alice)

    send_packet(carol, "msg", "carol", "hello alice", KEY)
    time.sleep(0.3)
    results.append(check("5. host peer receives too", any(p.get("content") == "hello alice" for p in read_all(alice)), ""))

    threads = [threading.Thread(target=spam, args=(conn, name, 40)) for conn, name in [(bob, "bob"), (carol, "carol")]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    time.sleep(0.6)
    stress = [p["content"] for p in read_all(alice, 3.0) if p.get("type") == "msg"]
    expected = {f"{name}-{i}" for name in ("bob", "carol") for i in range(40)}
    results.append(check("6. 80 concurrent messages arrive intact", set(stress) == expected, f"{len(stress)}/80 received"))

    carol.close()
    time.sleep(0.5)
    results.append(check("7. abrupt disconnect broadcasts leave", any("carol left" in p.get("content", "") for p in read_all(alice)), ""))
    results.append(check("8. roster drops the peer", "carol" not in room.names(), ", ".join(room.names())))

    bob.close()
    time.sleep(0.4)
    results.append(check("9. clean close broadcasts leave", any("bob left" in p.get("content", "") for p in read_all(alice)), ""))

    intruder = socket.socket()
    intruder.connect(("127.0.0.1", port))
    send_packet(intruder, "auth", "intruder", "", derive_key("wrong-secret"))
    time.sleep(0.5)
    results.append(check("10. wrong key cannot join", "intruder" not in room.names(), ", ".join(room.names())))
    results.append(check("11. intruder name never broadcast", not any("intruder" in p.get("content", "") for p in read_all(alice)), ""))
    intruder.close()

    read_all(duplicate)

    long_message = "z" * 500000
    send_packet(alice, "msg", "alice", long_message, KEY)
    time.sleep(0.5)
    big = [p for p in read_all(duplicate, 2.0) if p.get("type") == "msg"]
    results.append(check("12. 500KB message reassembled", len(big) == 1 and big[0]["content"] == long_message, f"{len(big[0]['content']) if big else 0} chars"))

    for conn in (alice, duplicate):
        conn.close()
    time.sleep(0.3)

    print()
    passed = sum(results)
    print(f"{passed}/{len(results)} passed")
    print("all good" if passed == len(results) else "failures above")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())