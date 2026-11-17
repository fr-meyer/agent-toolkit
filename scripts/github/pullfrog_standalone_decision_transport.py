"""Fixed-operation private Unix socket Decision relay, not a Gateway credential client.

No deployed relay is implied. The host relay must implement the documented SDK
owned call and return its untouched outcome and adapter-owned correlation receipt.
"""
from __future__ import annotations
import hmac
import json
import os
import secrets
import socket
import stat
import time
from concurrent.futures import CancelledError

import pullfrog_standalone_contract as contract
import pullfrog_standalone_decision_codec as codec

OPERATION = 'pullfrog.standalone.decision.v1'
MAX_BYTES = 131072

class TransportError(ValueError):
    pass


def _require(condition):
    if not condition:
        raise TransportError('decision_transport_refused')


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(TransportError('invalid_json')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise TransportError('invalid_relay_response') from exc


class DecisionTransport:
    """Callable provider. Pin private local destination and dedicated relay secret.

    Deliberately accepts no HTTP URL, redirects, Gateway token, agent override,
    arbitrary tool, or provider endpoint. Private parent directory and socket
    ownership prevent replacement by a different OS principal. Same-UID code is
    trusted. Socket authentication alone cannot qualify a provider or its cost.
    """
    def __init__(self, socket_path, *, relay_secret, destination_authorized=False,
                 clock=time.time, cancelled=lambda: False):
        _require(type(socket_path) is str and os.path.isabs(socket_path)
                 and os.path.normpath(socket_path) == socket_path)
        _require(type(relay_secret) is str and 32 <= len(relay_secret) <= 256
                 and relay_secret.isascii() and relay_secret.isprintable())
        _require(destination_authorized is True)
        self.path = socket_path
        self._secret = relay_secret
        self.clock = clock
        self.cancelled = cancelled
        self.last_receipt = None

    def _check_path(self):
        parent = os.path.dirname(self.path)
        # Reject symlink components, including ancestors.
        current = '/'
        for part in parent.split('/')[1:]:
            current = os.path.join(current, part)
            _require(not stat.S_ISLNK(os.lstat(current).st_mode))
        directory = os.stat(parent)
        target = os.lstat(self.path)
        _require(directory.st_uid == os.geteuid() and directory.st_mode & 0o077 == 0)
        _require(stat.S_ISSOCK(target.st_mode) and target.st_uid == os.geteuid()
                 and target.st_mode & 0o077 == 0)

    def __call__(self, payload):
        self.last_receipt = None
        now = int(self.clock())
        deadline = min(now + 30, payload.get('request', {}).get('expires_at', now))
        authority = dict(now=now, deadline=deadline, destination_authorized=True)
        batch, options = codec.encode(payload, **authority, cancelled=self.cancelled())
        self._check_path()
        nonce = secrets.token_hex(32)
        request = dict(operation=OPERATION, nonce=nonce, deadline=deadline,
                       payload_digest=contract.digest(payload), batch=batch, options=options)
        raw = json.dumps(request, allow_nan=False, separators=(',', ':')).encode()
        _require(len(raw) <= MAX_BYTES)
        # HMAC is over exact bytes, not reparsed JSON. Dedicated secret only.
        wire = json.dumps(dict(body=raw.decode(), mac=hmac.digest(
            self._secret.encode(), raw, 'sha256').hex()), separators=(',', ':')).encode() + b'\n'
        _require(len(wire) <= MAX_BYTES)
        stop = time.monotonic() + max(0, deadline - self.clock())
        def remaining():
            if self.cancelled():
                raise CancelledError()
            left = min(stop - time.monotonic(), deadline - self.clock())
            _require(left > 0)
            return min(left, 0.1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(remaining())
            sock.connect(self.path)
            # Linux peer credentials are mandatory, no unsupported fallback.
            import struct
            _require(hasattr(socket, 'SO_PEERCRED'))
            _, uid, _ = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            _require(uid == os.geteuid())
            sent = 0
            while sent < len(wire):
                sock.settimeout(remaining())
                try:
                    count = sock.send(wire[sent:])
                    _require(count > 0)
                    sent += count
                except socket.timeout:
                    continue
                _require(sent > 0)
            data = bytearray()
            while not data.endswith(b'\n'):
                sock.settimeout(remaining())
                try:
                    chunk = sock.recv(min(4096, MAX_BYTES + 1 - len(data)))
                except socket.timeout:
                    continue
                _require(bool(chunk))
                data.extend(chunk)
                _require(len(data) <= MAX_BYTES)
            remaining()
        envelope = _json(data)
        _require(type(envelope) is dict and set(envelope) == {'body', 'mac'})
        _require(type(envelope['body']) is str and type(envelope['mac']) is str)
        body = envelope['body'].encode()
        _require(hmac.compare_digest(envelope['mac'], hmac.digest(self._secret.encode(), body, 'sha256').hex()))
        reply = _json(body)
        _require(type(reply) is dict and set(reply) == {
            'operation', 'nonce', 'deadline', 'payload_digest', 'outcome', 'trusted_receipt'})
        for key in ('operation', 'nonce', 'deadline', 'payload_digest'):
            _require(type(reply[key]) is type(request[key]) and reply[key] == request[key])
        remaining()
        response, receipt = codec.decode(payload, reply['outcome'],
                                         trusted_receipt=reply['trusted_receipt'], **authority)
        remaining()
        self.last_receipt = receipt
        return response
