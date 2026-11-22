#!/usr/bin/env python3
"""Generate PARENT_PIN_HASH without accepting the PIN on the command line."""

from __future__ import annotations

import argparse
import getpass
import sys

from app.services.parent_auth_service import hash_parent_pin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read a parent PIN from a hidden prompt or stdin and print its PBKDF2 hash.")
    parser.parse_args(argv)
    pin = getpass.getpass("Parent PIN: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
    if not pin:
        parser.error("PIN must not be empty")
    print(hash_parent_pin(pin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
