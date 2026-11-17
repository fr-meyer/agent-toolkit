"""Local fake relay only. No provider invocation or qualification."""
import hmac
import json
import os
import socket
import tempfile
import threading
import unittest
from concurrent.futures import CancelledError
import test_pullfrog_standalone_decision_codec as fixtures
import pullfrog_standalone_decision_transport as transport

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CodecTests()
        self.fixture.setUp()
        self.root = tempfile.TemporaryDirectory(prefix='decision-', dir='/tmp')
        self.addCleanup(self.root.cleanup)
        self.path = self.root.name + '/relay'
        self.secret = 'fixture-only-not-a-credential-00000'

    def invoke(self, change=lambda reply: None, *, raw=None):
        server = socket.socket(socket.AF_UNIX)
        server.bind(self.path)
        os.chmod(self.path, 0o600)
        server.listen(1)
        errors = []
        def serve():
            try:
                with server:
                    connection, _ = server.accept()
                    with connection:
                        data = b''
                        while not data.endswith(b'\n'):
                            data += connection.recv(4096)
                        envelope = json.loads(data)
                        body = envelope['body'].encode()
                        assert hmac.compare_digest(envelope['mac'], hmac.digest(self.secret.encode(), body, 'sha256').hex())
                        request = json.loads(body)
                        assert request['options']['agentId'] == 'franck'
                        outcome = self.fixture.fixture()
                        reply = {key: request[key] for key in ('operation', 'nonce', 'deadline', 'payload_digest')}
                        reply.update(outcome=outcome, trusted_receipt=self.fixture.trusted(outcome))
                        change(reply)
                        response = json.dumps(reply).encode()
                        wire = json.dumps(dict(body=response.decode(), mac=hmac.digest(self.secret.encode(), response, 'sha256').hex())).encode() + b'\n'
                        connection.sendall(wire if raw is None else raw)
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        client = transport.DecisionTransport(self.path, relay_secret=self.secret,
                     destination_authorized=True, clock=lambda: 150)
        try:
            result = client(self.fixture.payload)
            return result, client.last_receipt
        finally:
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            os.unlink(self.path)

    def test_socket_roundtrip(self):
        result, receipt = self.invoke()
        self.assertEqual(result['outcome'], 'implement')
        self.assertFalse(receipt['cost_known'])

    def test_binding_and_provenance_refusals(self):
        for key, value in [('nonce', 'old'), ('operation', 'exec'), ('deadline', True),
                           ('payload_digest', 'wrong'), ('trusted_receipt', {}),
                           ('outcome', {'status': 'unknown'})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.invoke(lambda reply: reply.update({key: value}))

    def test_wire_refusals(self):
        for raw in (b'{}\n', b'{"body":"{}","mac":"wrong"}\n',
                    b'{"x":1,"x":2}\n', b'NaN\n', b'\xff\n', b'x' * 131073 + b'\n'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.invoke(raw=raw)

    def test_destination_and_secret(self):
        for path in ('https://example.org/tools/invoke', '/tmp/../relay'):
            with self.assertRaises(ValueError):
                transport.DecisionTransport(path, relay_secret=self.secret, destination_authorized=True)
        with self.assertRaises(ValueError):
            transport.DecisionTransport(self.path, relay_secret=self.secret)
        with self.assertRaises(ValueError):
            transport.DecisionTransport(self.path, relay_secret='short', destination_authorized=True)

    def test_cancel_before_io(self):
        client = transport.DecisionTransport(self.path, relay_secret=self.secret,
                    destination_authorized=True, clock=lambda: 150, cancelled=lambda: True)
        with self.assertRaises(CancelledError):
            client(self.fixture.payload)

    def test_stale_and_cancelled_response(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                original = transport.DecisionTransport
                state = {'time': 150, 'cancel': False}
                def factory(*args, **kwargs):
                    kwargs.update(clock=lambda: state['time'], cancelled=lambda: state['cancel'])
                    return original(*args, **kwargs)
                from unittest.mock import patch
                def change(reply):
                    state.update(time=150 if cancel else 181, cancel=cancel)
                with patch.object(transport, 'DecisionTransport', factory):
                    with self.assertRaises(CancelledError if cancel else ValueError):
                        self.invoke(change)

    def test_insecure_socket_directory(self):
        os.chmod(self.root.name, 0o755)
        client = transport.DecisionTransport(self.path, relay_secret=self.secret,
                    destination_authorized=True, clock=lambda: 150)
        with self.assertRaises(OSError):
            client(self.fixture.payload)

if __name__ == '__main__':
    unittest.main()
