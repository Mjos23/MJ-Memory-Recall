"""Atomic persistence, first-observation isolation and verified logical handoff."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from mj_memory_recall.store import EpisodicStore


def sample(namespace='project.alpha'):
    return {'profile': 'MJ-Memory-Recall/0.1.0', 'namespace': namespace, 'as_of': 100,
        'frame': {'id': 'local', 'x_min': '0', 'y_min': '0', 'width': '800', 'height': '600'},
        'memories': [{'id': 'memory-a', 'namespace': namespace, 'pattern': ['0.9'] * 9,
            'entity': 'robot', 'relation': 'inspection', 'context': 'bench', 'observed_at': 10,
            'available_at': 11, 'provenance': 'OBSERVED', 'receipt_ref': 'receipt-a',
            'selection_id': None, 'trace': []}],
        'query': {'id': 'query-a', 'observed_at': 100, 'cue': ['0.9'] * 9,
            'entity': 'robot', 'relation': 'inspection', 'context': 'bench',
            'previous_command': 'measure', 'events': []}}


class StoreContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'memory.sqlite'
        self.request = sample()

    def open(self, namespace='project.alpha', frame=None):
        return EpisodicStore(self.path, namespace=namespace, frame=frame or self.request['frame'])

    def test_restart_preserves_recall_and_exact_first_observation(self):
        with self.open() as store:
            store.append(self.request)
            self.assertEqual(store.snapshot(11)['memories'], [])
            self.assertEqual(len(store.snapshot(12)['memories']), 1)
        with self.open() as restarted:
            result = restarted.recall(self.request['query'], as_of=100)
            self.assertEqual(result['candidate'], 'memory-a')
            self.assertFalse(result['advisory_ready'])
            with self.assertRaises(ValueError):
                restarted.recall(self.request['query'], as_of=101)

    def test_namespace_and_exact_frame_are_isolated(self):
        with self.open() as alpha:
            alpha.append(self.request)
            other = sample('project.beta')
            with self.assertRaises(ValueError):
                alpha.append(other)
        with self.open(namespace='project.beta') as beta:
            self.assertEqual(beta.snapshot(100)['memories'], [])
            beta.append(sample('project.beta'))
        changed = deepcopy(self.request['frame'])
        changed['width'] = '801'
        with self.assertRaises(ValueError):
            self.open(frame=changed)

    def test_duplicate_late_in_append_rolls_back_entire_batch(self):
        with self.open() as store:
            store.append(self.request)
            batch = deepcopy(self.request)
            first = deepcopy(batch['memories'][0])
            first['id'] = 'would-have-been-inserted'
            batch['memories'].insert(0, first)
            with self.assertRaises(ValueError):
                store.append(batch)
            self.assertEqual([m['id'] for m in store.snapshot(100)['memories']], ['memory-a'])

    def test_lifecycle_checkpoint_recovery_and_generation_retention(self):
        with self.open() as store:
            store.append(self.request)
            with self.assertRaises(ValueError):
                store.advance('RECLAIM')
            store.advance('QUIESCE')
            with self.assertRaises(ValueError):
                store.append(self.request)
            store.advance('SEAL')
            checkpoint = store.checkpoint()
            digest = checkpoint['checkpoint_sha256']
        with self.open() as store:
            self.assertEqual(store.state['stage'], 'CHECKPOINT')
            self.assertEqual(store.recover(digest)['payload']['memories'], self.request['memories'])
            store.advance('DETACH')
            with self.assertRaises(ValueError):
                store.snapshot(100)
            with self.assertRaises(ValueError):
                store.advance('ACTIVATE')
            store.advance('RECLAIM')
            store.advance('ACTIVATE')
            self.assertEqual(store.state, {'stage': 'ACTIVE', 'generation': 1})
            self.assertEqual(store.snapshot(100)['memories'], [])
            self.assertTrue(store.recover(digest)['verified'])
            with self.assertRaises(ValueError):
                store.append(self.request)
            fresh = deepcopy(self.request)
            fresh['memories'][0]['id'] = 'memory-b'
            store.append(fresh)
        with closing(sqlite3.connect(self.path)) as database, database:
            rows = database.execute('SELECT generation, id FROM mj_memory_episodes ORDER BY generation').fetchall()
        self.assertEqual(rows, [(0, 'memory-a'), (1, 'memory-b')])
        self.assertTrue(self.path.exists())

    def test_tampered_record_is_detected_after_restart(self):
        with self.open() as store:
            store.append(self.request)
        with closing(sqlite3.connect(self.path)) as database, database:
            payload = deepcopy(self.request['memories'][0])
            payload['context'] = 'altered'
            database.execute('UPDATE mj_memory_episodes SET payload = ?', (json.dumps(payload),))
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.open()

    def test_tampered_checkpoint_blocks_recovery_and_detach(self):
        with self.open() as store:
            store.append(self.request)
            store.advance('QUIESCE')
            store.advance('SEAL')
            checkpoint = store.checkpoint()
            payload = deepcopy(checkpoint['payload'])
            payload['memories'][0]['context'] = 'altered'
            with closing(sqlite3.connect(self.path)) as database, database:
                database.execute('UPDATE mj_memory_checkpoints SET payload = ?', (json.dumps(payload),))
            with self.assertRaisesRegex(ValueError, 'integrity'):
                store.recover(checkpoint['checkpoint_sha256'])
            with self.assertRaises(ValueError):
                store.advance('DETACH')
            self.assertEqual(store.state['stage'], 'CHECKPOINT')


if __name__ == '__main__':
    unittest.main()
