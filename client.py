#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import sys

ENC = "utf-8"
LINE_END = "\n"

def send_line(conn: socket.socket, text: str) -> None:
    if not text.endswith(LINE_END):
        text += LINE_END
    conn.sendall(text.encode(ENC))

def recv_loop(conn: socket.socket) -> None:
    buf = bytearray()
    try:
        while True:
            idx = buf.find(b"\n")
            if idx != -1:
                line = buf[:idx]
                del buf[:idx+1]
                print(line.decode(ENC, errors="replace").rstrip("\r"))
                continue
            chunk = conn.recv(4096)
            if not chunk:
                print("SYS|Disconnected from server")
                return
            buf.extend(chunk)
    except OSError:
        return

def main():
    if len(sys.argv) < 4:
        print("Usage: python client.py <server_ip> <port> <name>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        t = threading.Thread(target=recv_loop, args=(s,), daemon=True)
        t.start()

        send_line(s, f"HELLO|{name}")

        while True:
            try:
                cmd = input()
            except EOFError:
                cmd = "QUIT"
            send_line(s, cmd)
            if cmd.strip() == "QUIT":
                break

if __name__ == "__main__":
    main()
