"""Workaround for a botasaurus_requests 4.0.38 bridge-server startup race.

The library starts a local Go HTTP bridge at import time. ``start_server``
hands the port to Go as a ``GoString`` backed by a local buffer, but Go reads
it asynchronously from a goroutine. The buffer can be garbage-collected first,
corrupting the port ("lookup tcp/<garbage>: Servname not supported") so the
bridge fails to bind and every request gets "Connection refused".

Patch ``start_server`` to keep the buffer alive for the object's lifetime, then
relaunch the bridge if the initial (unpatched) launch left it unreachable.
Import this module before importing ``botasaurus_requests.request``.
"""

import socket

from botasaurus_requests import cffi


def _start_server(self):
    # Retain the port buffer so Go's goroutine reads a valid port, not freed memory.
    self._port_ref = cffi.gostring(str(self.PORT))
    self.library.StartServer(self._port_ref)


def _bridge_alive(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(('127.0.0.1', port)) == 0


cffi.Library.start_server = _start_server

# The initial launch ran at import (unpatched) and may have bound a garbage port.
# Relaunch in place if the bridge is dead so client code keeps the same object.
if cffi.library is not None and not _bridge_alive(cffi.library.PORT):
    cffi.library.launch()
