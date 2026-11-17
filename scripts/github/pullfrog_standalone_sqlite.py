"""Local SQLite journal bridge. Not hosted-qualified or effect authority."""
import os
import sqlite3
from urllib.parse import quote
from contextlib import contextmanager
import pullfrog_standalone_store as core


class SQLiteBackend:
    def __init__(self, path, repository, pr_number, *, create=False):
        self.slot = core.FixtureBackend(repository, pr_number).slot
        self.path = os.path.abspath(os.fspath(path))
        self.lose_next_ack = False
        if create:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), slot BLOB NOT NULL, head BLOB)')
                db.execute('CREATE TABLE journal (sequence INTEGER PRIMARY KEY, receipt BLOB NOT NULL)')
                db.execute('INSERT INTO metadata VALUES (1, ?, NULL)', (core.canonical(self.slot),))
                db.commit()
        self.read()

    @contextmanager
    def _connection(self):
        try:
            db = sqlite3.connect('file:' + quote(self.path) + '?mode=rw', uri=True,
                                 timeout=5, isolation_level=None)
            try:
                core.require(db.execute("PRAGMA journal_mode").fetchone()[0] in ("delete", "wal"),
                             "unsafe_sqlite_journal_mode")
                db.execute('PRAGMA synchronous=FULL')
                core.require(db.execute("PRAGMA synchronous").fetchone()[0] == 2, "unsafe_sqlite_sync")
                yield db
            finally:
                db.close()
        except sqlite3.Error as exc:
            raise core.StoreError('sqlite_unavailable_or_corrupt') from exc

    def _load(self, db):
        rows = db.execute('SELECT slot, head FROM metadata WHERE id=1').fetchall()
        core.require(len(rows) == 1 and rows[0][0] == core.canonical(self.slot), 'slot_mismatch')
        fixture = core.FixtureBackend(self.slot['repository_slug'], self.slot['pr_number'])
        for sequence, raw in db.execute('SELECT sequence, receipt FROM journal ORDER BY sequence'):
            core.require(len(fixture.records) < core.MAX_RECORDS, 'history_capacity_retained')
            record = core.parse(raw)
            core.require(core.canonical(record) == raw, 'noncanonical_history')
            core.require(type(record) is dict and set(record) == {
                'document', 'digest', 'sequence', 'previous_digest', 'generation', 'ack_id'}, 'history_corrupt')
            core.require(type(record['sequence']) is int and record['sequence'] == sequence, 'history_chain')
            core.require(type(record.get('generation')) is int and record['generation'] > 0, 'invalid_fence')
            core.require(type(record.get('document')) is dict, 'history_corrupt')
            request = record['document'].get('request')
            core.require(type(request) is dict and all(request.get(k) == v for k, v in self.slot.items()), 'slot_mismatch')
            core.require(not fixture.records or record['generation'] >= fixture.records[-1]['generation'], 'stale_fence')
            fixture.records.append(record)
        fixture.status = 'present' if fixture.records else 'new_empty'
        last = fixture.read()
        core.require(rows[0][1] == (core.canonical(last) if last else None), 'history_head_mismatch')
        return fixture

    def read(self):
        with self._connection() as db:
            db.execute('BEGIN')
            return self._load(db).read()

    @property
    def records(self):
        with self._connection() as db:
            db.execute('BEGIN')
            return self._load(db).records


class Store:
    def __init__(self, backend, *, trusted_reducers=(), generation=1):
        core.require(type(backend) is SQLiteBackend, 'unqualified_backend')
        trusted_reducers = tuple(trusted_reducers)
        core.Store(core.FixtureBackend(backend.slot['repository_slug'], backend.slot['pr_number']),
                   trusted_reducers=trusted_reducers, generation=generation)
        self.backend, self.reducers, self.generation = backend, trusted_reducers, generation
        self._controller_scope = None

    def transaction(self, expected_digest, transform):
        b = self.backend
        with b._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            fixture = b._load(db)
            trusted = core.Store(fixture, trusted_reducers=self.reducers, generation=self.generation)
            trusted._controller_scope = self._controller_scope
            result = trusted.transaction(expected_digest, transform)
            if result['changed']:
                receipt = fixture.read()
                raw = core.canonical(receipt)
                db.execute('INSERT INTO journal VALUES (?, ?)', (receipt['sequence'], raw))
                db.execute('UPDATE metadata SET head=? WHERE id=1', (raw,))
            try:
                db.commit()
            except sqlite3.Error as exc:
                raise core.StoreError("ambiguous_ack_reconcile_required") from exc
            if b.lose_next_ack:
                b.lose_next_ack = False
                raise core.StoreError('ambiguous_ack_reconcile_required')
            db.execute('BEGIN')
            core.require(b._load(db).read() == fixture.read(), 'ambiguous_ack_reconcile_required')
        result.update(durability='local_sqlite_full', hosted_effect_allowed=False)
        return result

    def authorize_hosted_effect(self, acknowledgement):
        raise core.StoreError('hosted_store_unqualified')


class _Transaction:
    def __init__(self, backend, generation, operation):
        self.backend, self.generation, self.operation = backend, generation, operation
        self.active = True

    def transaction(self, expected_digest, transform):
        core.require(self.active, 'controller_operation_closed')
        store = Store(self.backend, trusted_reducers=(transform,), generation=self.generation)
        store._controller_scope = (core._CONTROLLER, self.operation)
        return store.transaction(expected_digest, transform)


class ControllerAdapter:
    def __init__(self, backend, *, generation=1):
        Store(backend, generation=generation)
        self._backend, self._generation = backend, generation

    def _call(self, operation, *args, **kwargs):
        core.require(operation in ("advance", "decide", "bind_publication", "reconcile"), "unknown_operation")
        import pullfrog_standalone_controller as controller
        proxy = _Transaction(self._backend, self._generation, operation)
        try:
            return getattr(controller, operation)(proxy, *args, **kwargs)
        finally:
            proxy.active = False

    def advance(self, request, event, policy, *, expected_digest, now):
        return self._call('advance', request, event, policy, expected_digest=expected_digest, now=now)

    def decide(self, policy, context, execution, destination, *, expected_digest, now, provider=None, clock=None):
        return self._call('decide', policy, context, execution, destination,
                          expected_digest=expected_digest, now=now, provider=provider, clock=clock)

    def bind_publication(self, candidate, *, expected_digest, now):
        return self._call('bind_publication', candidate, expected_digest=expected_digest, now=now)

    def reconcile(self, observation, policy, *, expected_digest, now):
        return self._call('reconcile', observation, policy, expected_digest=expected_digest, now=now)
