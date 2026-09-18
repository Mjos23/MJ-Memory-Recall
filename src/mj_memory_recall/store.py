"""SQLite episodic I/O with immutable rows and native lifecycle authorization."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from . import engine, kernel

CHECKPOINT_PROFILE = 'MJ-Memory-Checkpoint/0.1.0'
MAX_GENERATION_RECORDS = 256
MAX_RECORD_BYTES = 65536
MAX_CHECKPOINT_BYTES = 16777216


class EpisodicStore:
    """One explicit namespace/frame per connection; separate connections per thread.

    Construction creates a local SQLite store only at the caller's chosen path.
    All records are retained through logical detach/reclaim. This class neither
    deletes user files nor installs models or grants action permission.
    """

    def __init__(self, path, *, namespace, frame):
        self.namespace = engine.identifier(namespace, 'namespace')
        engine.validate_frame(frame)
        self._frame = deepcopy(frame)
        self.path = Path(path)
        self._db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self._db.execute('PRAGMA foreign_keys = ON')
        self._db.execute('PRAGMA synchronous = FULL')
        try:
            with self._transaction(write=True):
                self._db.execute('CREATE TABLE IF NOT EXISTS mj_memory_namespaces ('
                    'namespace TEXT PRIMARY KEY, frame TEXT NOT NULL, frame_sha256 TEXT NOT NULL, '
                    'state TEXT NOT NULL, state_sha256 TEXT NOT NULL)')
                self._db.execute('CREATE TABLE IF NOT EXISTS mj_memory_episodes ('
                    'namespace TEXT NOT NULL, id TEXT NOT NULL, generation INTEGER NOT NULL, '
                    'payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL, '
                    'PRIMARY KEY(namespace, id), FOREIGN KEY(namespace) REFERENCES mj_memory_namespaces(namespace))')
                self._db.execute('CREATE TABLE IF NOT EXISTS mj_memory_checkpoints ('
                    'namespace TEXT NOT NULL, generation INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, '
                    'payload TEXT NOT NULL, PRIMARY KEY(namespace, generation), '
                    'FOREIGN KEY(namespace) REFERENCES mj_memory_namespaces(namespace))')
                row = self._db.execute('SELECT namespace FROM mj_memory_namespaces WHERE namespace = ?',
                                       (self.namespace,)).fetchone()
                if row is None:
                    initial = kernel.transition({'stage': 'UNINITIALIZED', 'generation': 0}, 'INIT')['state']
                    state = {'lifecycle': initial, 'checkpoint_sha256': None}
                    self._db.execute('INSERT INTO mj_memory_namespaces VALUES (?, ?, ?, ?, ?)',
                        (self.namespace, engine.canonical(self._frame), engine.request_digest(self._frame),
                         engine.canonical(state), self._state_digest(state)))
                state = self._read_state()
                self._records(state['lifecycle']['generation'])
                if state['checkpoint_sha256'] is not None:
                    self._verify_checkpoint(state['checkpoint_sha256'])
        except Exception:
            self._db.close()
            raise

    @property
    def frame(self):
        return deepcopy(self._frame)

    @property
    def state(self):
        with self._transaction():
            return deepcopy(self._read_state()['lifecycle'])

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self, *, write=False):
        self._db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield
            self._db.execute('COMMIT')
        except BaseException:
            self._db.execute('ROLLBACK')
            raise

    def _state_digest(self, state):
        return engine.request_digest({'namespace': self.namespace, 'frame': self._frame, 'state': state})

    def _read_state(self):
        row = self._db.execute('SELECT frame, frame_sha256, state, state_sha256 FROM mj_memory_namespaces '
                               'WHERE namespace = ?', (self.namespace,)).fetchone()
        if row is None:
            raise ValueError('Missing memory namespace')
        frame, state = json.loads(row[0]), json.loads(row[2])
        if frame != self._frame or engine.request_digest(frame) != row[1]:
            raise ValueError('Memory coordinate frame differs or failed integrity verification')
        engine.shape(state, ('lifecycle', 'checkpoint_sha256'), 'stored state')
        engine.shape(state['lifecycle'], ('stage', 'generation'), 'stored lifecycle')
        engine.identifier(state['lifecycle']['stage'], 'stage')
        engine.integer(state['lifecycle']['generation'], 'generation', 1000000)
        if state['checkpoint_sha256'] is not None:
            kernel._hash(state['checkpoint_sha256'], 'checkpoint')
        if self._state_digest(state) != row[3]:
            raise ValueError('Memory lifecycle integrity mismatch')
        return state

    def _write_state(self, lifecycle, checkpoint_sha256):
        state = {'lifecycle': lifecycle, 'checkpoint_sha256': checkpoint_sha256}
        self._db.execute('UPDATE mj_memory_namespaces SET state = ?, state_sha256 = ? WHERE namespace = ?',
                         (engine.canonical(state), self._state_digest(state), self.namespace))

    def _validate_memories(self, memories):
        for start in range(0, len(memories), 16):
            batch = memories[start:start + 16]
            as_of = max(item['available_at'] for item in batch) + 1
            ids = {item['id'] for item in batch}
            query_id = next('store-validation-' + str(i) for i in range(17)
                            if 'store-validation-' + str(i) not in ids)
            engine.validate({'profile': engine.PROFILE, 'namespace': self.namespace, 'as_of': as_of,
                'frame': self._frame, 'memories': batch,
                'query': {'id': query_id, 'observed_at': as_of, 'cue': [None] * 9,
                          'entity': None, 'relation': None, 'context': None,
                          'previous_command': 'measure', 'events': []}})

    def _records(self, generation):
        rows = self._db.execute('SELECT id, payload, payload_sha256 FROM mj_memory_episodes '
            'WHERE namespace = ? AND generation = ? ORDER BY id', (self.namespace, generation)).fetchall()
        if len(rows) > MAX_GENERATION_RECORDS:
            raise ValueError('Memory generation exceeds its bounded record capacity')
        records = []
        for identity, payload, expected in rows:
            if len(payload.encode('utf-8')) > MAX_RECORD_BYTES:
                raise ValueError('Stored record exceeds its byte bound')
            record = json.loads(payload)
            actual = engine.request_digest({'namespace': self.namespace, 'generation': generation, 'record': record})
            if record.get('id') != identity or record.get('namespace') != self.namespace or actual != expected:
                raise ValueError('Memory record integrity mismatch')
            records.append(record)
        self._validate_memories(records)
        return records

    def append(self, request):
        """Atomically append the validated request's memories, never overwrite IDs."""
        request = deepcopy(engine.validate(deepcopy(request)))
        if request['namespace'] != self.namespace or request['frame'] != self._frame:
            raise ValueError('Request does not match the store namespace and exact frame')
        encoded = [(record, engine.canonical(record)) for record in request['memories']]
        if any(len(payload.encode('utf-8')) > MAX_RECORD_BYTES for _, payload in encoded):
            raise ValueError('Record exceeds 65536 bytes')
        with self._transaction(write=True):
            state = self._read_state()['lifecycle']
            authorization = kernel.authorize(state, 'APPEND')
            if len(self._records(state['generation'])) + len(encoded) > MAX_GENERATION_RECORDS:
                raise ValueError('Memory generation record capacity exceeded')
            try:
                for record, payload in encoded:
                    digest = engine.request_digest({'namespace': self.namespace, 'generation': state['generation'], 'record': record})
                    self._db.execute('INSERT INTO mj_memory_episodes VALUES (?, ?, ?, ?, ?)',
                        (self.namespace, record['id'], state['generation'], payload, digest))
            except sqlite3.IntegrityError as error:
                raise ValueError('Immutable memory ID already exists in this namespace') from error
        return {'appended': len(encoded), 'generation': state['generation'],
                'request_sha256': engine.request_digest(request), **authorization}

    def snapshot(self, as_of):
        """Read one atomic, bounded view strictly before the first observation."""
        engine.integer(as_of, 'as_of')
        with self._transaction():
            state = self._read_state()['lifecycle']
            authorization = kernel.authorize(state, 'SNAPSHOT')
            memories = [item for item in self._records(state['generation']) if item['available_at'] < as_of]
            if len(memories) > 16:
                raise ValueError('Eligible snapshot exceeds the recall profile; use a narrower namespace')
            snapshot = {'profile': 'MJ-Memory-Snapshot/0.1.0', 'namespace': self.namespace,
                'frame': self.frame, 'generation': state['generation'], 'as_of': as_of, 'memories': memories}
        return {**snapshot, 'snapshot_sha256': engine.request_digest(snapshot), **authorization}

    def request_for(self, query, *, as_of):
        snapshot = self.snapshot(as_of)
        request = {'profile': engine.PROFILE, 'namespace': self.namespace, 'as_of': as_of,
                   'frame': self.frame, 'memories': snapshot['memories'], 'query': deepcopy(query)}
        return engine.validate(request)

    def recall(self, query, *, as_of, review=None, include_receipt=False):
        return engine.recall(self.request_for(query, as_of=as_of), review=review, include_receipt=include_receipt)

    def _verify_checkpoint(self, expected):
        kernel._hash(expected, 'checkpoint_sha256')
        row = self._db.execute('SELECT generation, payload FROM mj_memory_checkpoints '
            'WHERE namespace = ? AND sha256 = ?', (self.namespace, expected)).fetchone()
        if row is None or len(row[1].encode('utf-8')) > MAX_CHECKPOINT_BYTES:
            raise ValueError('Checkpoint is missing or exceeds its byte bound')
        payload = json.loads(row[1])
        engine.shape(payload, ('profile', 'namespace', 'frame', 'generation', 'memories'), 'checkpoint')
        if (payload['profile'] != CHECKPOINT_PROFILE or payload['namespace'] != self.namespace or
                payload['frame'] != self._frame or payload['generation'] != row[0] or
                engine.request_digest(payload) != expected):
            raise ValueError('Checkpoint SHA or scope integrity mismatch')
        if payload['memories'] != self._records(row[0]):
            raise ValueError('Checkpoint no longer matches its retained generation')
        return payload

    def checkpoint(self):
        """Atomically seal a content hash and advance SEAL to CHECKPOINT."""
        with self._transaction(write=True):
            old = self._read_state()['lifecycle']
            payload = {'profile': CHECKPOINT_PROFILE, 'namespace': self.namespace, 'frame': self.frame,
                       'generation': old['generation'], 'memories': self._records(old['generation'])}
            encoded = engine.canonical(payload)
            if len(encoded.encode('utf-8')) > MAX_CHECKPOINT_BYTES:
                raise ValueError('Checkpoint exceeds its byte bound')
            digest = engine.request_digest(payload)
            accepted = kernel.transition(old, 'CHECKPOINT', checkpoint_valid=True)
            self._db.execute('INSERT INTO mj_memory_checkpoints VALUES (?, ?, ?, ?)',
                             (self.namespace, old['generation'], digest, encoded))
            self._write_state(accepted['state'], digest)
        return {'checkpoint_sha256': digest, 'payload': payload, **accepted}

    def advance(self, stage):
        """Perform a native-approved lifecycle step; CHECKPOINT uses checkpoint()."""
        if stage == 'CHECKPOINT':
            return self.checkpoint()
        with self._transaction(write=True):
            old = self._read_state()
            checkpoint_valid = False
            if old['checkpoint_sha256'] is not None:
                payload = self._verify_checkpoint(old['checkpoint_sha256'])
                checkpoint_valid = payload['generation'] == old['lifecycle']['generation']
            accepted = kernel.transition(old['lifecycle'], stage, checkpoint_valid=checkpoint_valid)
            checkpoint = old['checkpoint_sha256']
            if accepted['state']['generation'] != old['lifecycle']['generation']:
                checkpoint = None
            self._write_state(accepted['state'], checkpoint)
        return accepted

    def recover(self, checkpoint_sha256):
        """Verify retained recovery material against a separately retained hash.

        Returns an immutable snapshot; does not reactivate an old generation or
        bypass QUIESCE/SEAL/CHECKPOINT/DETACH/RECLAIM.
        """
        with self._transaction():
            self._read_state()
            payload = self._verify_checkpoint(checkpoint_sha256)
        return {'checkpoint_sha256': checkpoint_sha256, 'payload': deepcopy(payload), 'verified': True}
