#!/usr/bin/env python3
"""CLI tool to send test packets to the RPi UDP server.

Usage:
    python udp_test_client.py <rpi_ip> [port]

Interactive commands:
    m <dx> <dy>       - Mouse move
    c                 - Left click
    r                 - Right click
    s <amount>        - Scroll (positive=up, negative=down)
    u / d / l / ri    - Arrow up/down/left/right
    e                 - Enter
    home              - Home (Cmd+H)
    tab               - App switch (Cmd+Tab)
    q                 - Quit
"""

import socket
import struct
import sys

PACK = struct.Struct("<BBbbbB")

# USB HID keycodes
KEY_ENTER = 0x28
KEY_RIGHT = 0x4F
KEY_LEFT = 0x50
KEY_DOWN = 0x51
KEY_UP = 0x52
KEY_H = 0x0B
KEY_TAB = 0x2B
MOD_GUI = 0x08


def build(mode, flags, dx, dy, wheel, keycode):
    return PACK.pack(mode, flags, dx, dy, wheel, keycode)


def send_key(sock, addr, mode, flags, keycode):
    """Send a key press followed by a release."""
    sock.sendto(build(mode, flags, 0, 0, 0, keycode), addr)
    sock.sendto(build(mode, 0, 0, 0, 0, 0), addr)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5005
    addr = (host, port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Sending to {host}:{port}")
    print("Commands: m <dx> <dy> | c | r | s <amt> | u/d/l/ri | e | home | tab | q")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "q":
            break
        elif cmd == "m" and len(parts) >= 3:
            dx = int(parts[1])
            dy = int(parts[2])
            sock.sendto(build(0, 0, dx, dy, 0, 0), addr)
        elif cmd == "c":
            sock.sendto(build(0, 0x01, 0, 0, 0, 0), addr)
            sock.sendto(build(0, 0x00, 0, 0, 0, 0), addr)
        elif cmd == "r":
            sock.sendto(build(0, 0x02, 0, 0, 0, 0), addr)
            sock.sendto(build(0, 0x00, 0, 0, 0, 0), addr)
        elif cmd == "s" and len(parts) >= 2:
            amt = int(parts[1])
            sock.sendto(build(1, 0, 0, 0, amt, 0), addr)
        elif cmd == "u":
            send_key(sock, addr, 2, 0, KEY_UP)
        elif cmd == "d":
            send_key(sock, addr, 2, 0, KEY_DOWN)
        elif cmd == "l":
            send_key(sock, addr, 2, 0, KEY_LEFT)
        elif cmd == "ri":
            send_key(sock, addr, 2, 0, KEY_RIGHT)
        elif cmd == "e":
            send_key(sock, addr, 2, 0, KEY_ENTER)
        elif cmd == "home":
            send_key(sock, addr, 0, MOD_GUI, KEY_H)
        elif cmd == "tab":
            send_key(sock, addr, 0, MOD_GUI, KEY_TAB)
        else:
            print("Unknown command. Try: m/c/r/s/u/d/l/ri/e/home/tab/q")

    sock.close()
    print("Bye.")


if __name__ == "__main__":
    main()
