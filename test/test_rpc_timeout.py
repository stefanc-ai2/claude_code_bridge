"""Tests for RPC timeout handling."""
from __future__ import annotations

import socket
import threading
import time

import pytest

from askd_rpc import CCBTimeoutError, _recv_with_deadline


def test_recv_with_deadline_returns_on_newline():
    """Test that _recv_with_deadline returns when newline is received."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    def server():
        conn, _ = server_sock.accept()
        time.sleep(0.1)
        conn.sendall(b'{"result": "ok"}\n')
        conn.close()
        server_sock.close()

    t = threading.Thread(target=server, daemon=True)
    t.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    deadline = time.time() + 5.0
    buf = _recv_with_deadline(client, deadline)
    client.close()
    t.join(timeout=1.0)

    assert b"\n" in buf
    assert b"ok" in buf


def test_recv_with_deadline_raises_on_timeout():
    """Test that _recv_with_deadline raises CCBTimeoutError when deadline exceeded."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    def server():
        conn, _ = server_sock.accept()
        # Send partial data without newline, then hang
        conn.sendall(b'{"partial": true')
        time.sleep(3.0)  # Longer than client deadline
        conn.close()
        server_sock.close()

    t = threading.Thread(target=server, daemon=True)
    t.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    deadline = time.time() + 0.5  # Short deadline

    with pytest.raises(CCBTimeoutError):
        _recv_with_deadline(client, deadline)

    client.close()
    t.join(timeout=1.0)


def test_recv_with_deadline_handles_connection_close():
    """Test that _recv_with_deadline handles server closing connection."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    def server():
        conn, _ = server_sock.accept()
        conn.sendall(b'partial')
        conn.close()  # Close without newline
        server_sock.close()

    t = threading.Thread(target=server, daemon=True)
    t.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    deadline = time.time() + 5.0
    buf = _recv_with_deadline(client, deadline)
    client.close()
    t.join(timeout=1.0)

    # Should return partial data (no newline)
    assert b"partial" in buf
    assert b"\n" not in buf


def test_ccb_timeout_error_is_timeout_error():
    """Test that CCBTimeoutError is a subclass of TimeoutError."""
    assert issubclass(CCBTimeoutError, TimeoutError)
    err = CCBTimeoutError("test message")
    assert str(err) == "test message"


def test_recv_with_deadline_raises_on_max_bytes_exceeded():
    """Test that _recv_with_deadline raises ValueError when max_bytes exceeded."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    def server():
        conn, _ = server_sock.accept()
        # Send lots of data without newline
        conn.sendall(b"x" * 200)
        conn.close()
        server_sock.close()

    t = threading.Thread(target=server, daemon=True)
    t.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    deadline = time.time() + 5.0

    with pytest.raises(ValueError, match="max_bytes"):
        _recv_with_deadline(client, deadline, max_bytes=100)

    client.close()
    t.join(timeout=1.0)
