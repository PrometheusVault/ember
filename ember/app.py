# ember/app.py
import os
import sys
from textwrap import dedent

VAULT_DIR = os.environ.get("VAULT_DIR", "/vault")


def print_banner():
    banner = dedent(
        f"""
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃  Prometheus Vault – Ember (dev stub)     ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
        Vault dir : {VAULT_DIR}
        Mode      : DEV (Docker)
        """
    ).strip()
    print(banner)
    print()

def main():
    print_banner()
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            line = input("EMBER> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Exiting Ember]")
            break

        if line.lower() in {"quit", "exit"}:
            print("[Goodbye]")
            break

        if not line:
            continue

        # For now, just echo. Later this is where we:
        #  - send to planner model
        #  - run tools
        #  - send to answer model
        print(f"[echo] You said: {line}")
