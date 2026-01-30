from __future__ import annotations

import json
import socket
import time
from pathlib import Path


class CCBTimeoutError(TimeoutError):
    """Raised when a CCB RPC operation times out."""
    pass


def read_state(state_file: Path) -> dict | None:
    try:
        raw = state_file.read_text(encoding="utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _recv_with_deadline(
    sock: socket.socket,
    deadline: float,
    bufsize: int = 4096,
    max_bytes: int = 16 * 1024 * 1024,  # 16 MB default max
) -> bytes:
    """Receive data with per-recv timeout honoring overall deadline.

    Args:
        sock: Connected socket to receive from.
        deadline: Absolute deadline (from time.time()) after which CCBTimeoutError is raised.
        bufsize: Size of each recv() call.
        max_bytes: Maximum total bytes to receive (guards against unbounded memory growth).

    Returns:
        Bytes received (may or may not contain newline depending on connection close).

    Raises:
        CCBTimeoutError: If deadline is exceeded before newline received.
        ValueError: If max_bytes exceeded before newline received.
    """
    buf = b""
    while b"\n" not in buf:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise CCBTimeoutError("recv deadline exceeded")
        # Set per-recv timeout to remaining time, capped at 1s for responsiveness
        sock.settimeout(min(remaining, 1.0))
        try:
            chunk = sock.recv(bufsize)
        except socket.timeout:
            continue  # Check deadline and retry
        if not chunk:
            break  # Connection closed
        buf += chunk
        if len(buf) > max_bytes:
            raise ValueError(f"recv exceeded max_bytes ({max_bytes})")
    return buf


def ping_daemon(protocol_prefix: str, timeout_s: float, state_file: Path) -> bool:
    st = read_state(state_file)
    if not st:
        return False
    try:
        host = st.get("connect_host") or st["host"]
        port = int(st["port"])
        token = st["token"]
    except Exception:
        return False
    try:
        deadline = time.time() + timeout_s
        with socket.create_connection((host, port), timeout=min(timeout_s, 2.0)) as sock:
            req = {"type": f"{protocol_prefix}.ping", "v": 1, "id": "ping", "token": token}
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            buf = _recv_with_deadline(sock, deadline, bufsize=1024)
            if b"\n" not in buf:
                return False
            line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            resp = json.loads(line)
            return resp.get("type") in (f"{protocol_prefix}.pong", f"{protocol_prefix}.response") and int(resp.get("exit_code") or 0) == 0
    except CCBTimeoutError:
        return False
    except Exception:
        return False


def shutdown_daemon(protocol_prefix: str, timeout_s: float, state_file: Path) -> bool:
    st = read_state(state_file)
    if not st:
        return False
    try:
        host = st.get("connect_host") or st["host"]
        port = int(st["port"])
        token = st["token"]
    except Exception:
        return False
    try:
        deadline = time.time() + timeout_s
        with socket.create_connection((host, port), timeout=min(timeout_s, 2.0)) as sock:
            req = {"type": f"{protocol_prefix}.shutdown", "v": 1, "id": "shutdown", "token": token}
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            # Best-effort read response with deadline
            try:
                _ = _recv_with_deadline(sock, deadline, bufsize=1024)
            except CCBTimeoutError:
                pass  # Shutdown sent, response optional
        return True
    except CCBTimeoutError:
        return False
    except Exception:
        return False
