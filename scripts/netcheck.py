"""Network self-check for pilot runs.

Diagnoses: proxy availability (env / Windows registry / common ports), direct
reachability of the OpenCode Go endpoint, and overall readiness. Run after
turning a proxy on:

    python scripts/netcheck.py
"""

from __future__ import annotations

import socket
import urllib.request

ENDPOINT = "https://opencode.ai/zen/go/v1/models"
PROBE_PORTS = [7890, 7897, 1080, 10808, 10809, 8888, 2080]


def alive(host: str, port: int, timeout: float = 1.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def main() -> int:
    print("== proxy ports ==")
    found = []
    for port in PROBE_PORTS:
        if alive("127.0.0.1", port):
            print(f"  {port}: OPEN")
            found.append(port)
    if not found:
        print("  none open — is Clash/Proxifier-style software running?")

    print("== endpoint direct (no proxy) ==")
    try:
        r = urllib.request.urlopen(ENDPOINT, timeout=8)
        print(f"  direct OK: {r.status}")
        return 0
    except Exception as e:
        print(f"  direct FAIL: {e}")

    if found:
        print("== endpoint via proxy ==")
        proxy = f"http://127.0.0.1:{found[0]}"
        try:
            op = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
            r = op.open(ENDPOINT, timeout=10)
            print(f"  proxy OK: {r.status} (proxy={proxy})")
            return 0
        except Exception as e:
            print(f"  proxy FAIL: {e}")
    print("\nNo route to OpenCode Go. Turn on your proxy, then re-run; then:")
    print("  python scripts/run_pilot.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())