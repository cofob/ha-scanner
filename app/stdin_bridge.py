#!/usr/bin/env python3
"""Bridge hassio.addon_stdin input to the scanner daemon via a Unix socket."""

import socket
import sys
import time
from pathlib import Path


SOCKET_PATH = Path("/tmp/ha_stdin.sock")


def wait_for_socket() -> socket.socket:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    while True:
        try:
            client.sendto(b"", str(SOCKET_PATH))
            return client
        except FileNotFoundError:
            time.sleep(0.1)
        except OSError:
            time.sleep(0.1)


def main() -> None:
    client = wait_for_socket()
    for line in sys.stdin:
        client.sendto(line.encode("utf-8"), str(SOCKET_PATH))


if __name__ == "__main__":
    main()
