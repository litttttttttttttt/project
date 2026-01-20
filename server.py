#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
from typing import Dict, Tuple

HOST = "0.0.0.0"
PORT = 5000
BACKLOG = 50
ENC = "utf-8"
LINE_END = "\n"

clients: Dict[str, Tuple[socket.socket, Tuple[str, int]]] = {}
clients_lock = threading.Lock()


def send_line(conn: socket.socket, text: str) -> None:
    if not text.endswith(LINE_END):
        text += LINE_END
    conn.sendall(text.encode(ENC))


def recv_line(conn: socket.socket, buffer: bytearray) -> str | None:
    while True:
        idx = buffer.find(b"\n")
        if idx != -1:
            line = buffer[:idx]
            del buffer[: idx + 1]
            return line.decode(ENC, errors="replace").rstrip("\r")

        chunk = conn.recv(4096)
        if not chunk:
            return None
        buffer.extend(chunk)


def broadcast_system(message: str, exclude: str | None = None) -> None:
    with clients_lock:
        items = list(clients.items())
    for name, (c, _) in items:
        if exclude is not None and name == exclude:
            continue
        try:
            send_line(c, f"SYS|{message}")
        except OSError:
            pass


def remove_client(name: str) -> None:
    with clients_lock:
        info = clients.pop(name, None)
    if info:
        conn, _ = info
        try:
            conn.close()
        except OSError:
            pass
        broadcast_system(f"{name} disconnected", exclude=name)


def register_client(conn: socket.socket, addr: Tuple[str, int], buffer: bytearray) -> str | None:
    send_line(conn, "SYS|Welcome. Identify with: HELLO|<your_name>")
    line = recv_line(conn, buffer)
    if line is None:
        return None

    if not line.startswith("HELLO|"):
        send_line(conn, "ERR|First message must be HELLO|<name>")
        return None

    name = line.split("|", 1)[1].strip()
    if not name:
        send_line(conn, "ERR|Name cannot be empty")
        return None

    with clients_lock:
        if name in clients:
            send_line(conn, "ERR|Name already in use")
            return None
        clients[name] = (conn, addr)

    send_line(conn, f"OK|Registered as {name}")
    broadcast_system(f"{name} connected", exclude=name)
    return name


def handle_client(conn: socket.socket, addr: Tuple[str, int]) -> None:
    buffer = bytearray()
    name = None

    try:
        name = register_client(conn, addr, buffer)
        if name is None:
            conn.close()
            return

        send_line(conn, "SYS|Commands: LIST, SEND|to|msg, QUIT")

        while True:
            line = recv_line(conn, buffer)
            if line is None:
                break

            line = line.strip()
            if not line:
                continue

            if line == "QUIT":
                send_line(conn, "OK|Bye")
                break

            if line == "LIST":
                with clients_lock:
                    names = ",".join(sorted(clients.keys()))
                send_line(conn, f"USERS|{names}")
                continue

            if line.startswith("SEND|"):
                parts = line.split("|", 2)
                if len(parts) != 3:
                    send_line(conn, "ERR|Format: SEND|<to>|<message>")
                    continue

                to_name = parts[1].strip()
                msg = parts[2]

                with clients_lock:
                    target = clients.get(to_name)

                if target is None:
                    send_line(conn, f"ERR|User '{to_name}' not found")
                    continue

                target_conn, _ = target
                try:
                    send_line(target_conn, f"FROM|{name}|{msg}")
                    send_line(conn, f"OK|Sent to {to_name}")
                except OSError:
                    send_line(conn, f"ERR|Failed to deliver to {to_name}")
                continue

            send_line(conn, "ERR|Unknown command. Use LIST, SEND|to|msg, QUIT")

    except (ConnectionResetError, OSError):
        pass
    finally:
        if name is not None:
            remove_client(name)
        else:
            try:
                conn.close()
            except OSError:
                pass


def main() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(BACKLOG)

        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    main()
