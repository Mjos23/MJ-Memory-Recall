"""Public native recall contracts; geometric expectations are independently chosen."""
from copy import deepcopy
from decimal import Decimal
import unittest

from mj_memory_recall import recall


def request():
    cue = ['0.9'] * 9
    def event(actor, step, x, y, token='derive'):
        return {'actor': actor, 'step': step, 'position': [str(x), str(y)], 'command': token}
    events = [event('sensor', i, 100 + i * 60, 150 + i * 20) for i in range(3)]
    memories = []
    for name, offset in [('a', 0), ('b', 300)]:
        trace = [event('sensor', i, 100 + i * 60 + offset, 150 + i * 20) for i in range(3)]
        memories.append({'id': 'memory-' + name, 'namespace': 'robotics.lab', 'pattern': cue,
            'entity': 'robot', 'relation': 'inspection', 'context': 'bench',
            'observed_at': 10, 'available_at': 11, 'provenance': 'OBSERVED',
            'receipt_ref': 'fixture-' + name, 'selection_id': None, 'trace': trace})
    return {'profile': 'MJ-Memory-Recall/0.1.0', 'namespace': 'robotics.lab', 'as_of': 100,
        'frame': {'id': 'local-grid', 'x_min': '0', 'y_min': '0', 'width': '800', 'height': '600'},
        'memories': memories, 'query': {'id': 'query-1', 'observed_at': 100,
            'cue': cue, 'entity': 'robot', 'relation': 'inspection', 'context': 'bench',
            'previous_command': 'measure', 'events': events}}


class RecallContracts(unittest.TestCase):
    def test_sequence_recovers_an_associative_tie(self):
        result = recall(request())
        self.assertFalse(result['baseline_available'])
        self.assertEqual(result['candidate'], 'memory-a')
        self.assertTrue(result['match_available'])
        self.assertEqual(result['status'], 'RECALLED')
        self.assertFalse(result['advisory_ready'])

    def test_equal_paths_do_not_imply_identity(self):
        value = request()
        value['memories'][1]['trace'] = deepcopy(value['memories'][0]['trace'])
        result = recall(value)
        self.assertIsNone(result['candidate'])
        self.assertEqual(result['status'], 'AMBIGUOUS')

    def test_unknown_context_does_not_become_observed_context(self):
        value = request()
        value['query']['context'] = None
        result = recall(value)
        self.assertEqual(result['candidate'], 'memory-a')
        self.assertFalse(result['match_available'])
        self.assertEqual(result['status'], 'CONTEXT_HOLD')

    def test_other_namespace_never_leaks_into_recall(self):
        value = request()
        value['memories'][0]['namespace'] = 'other.project'
        with self.assertRaises(ValueError):
            recall(value)

    def test_future_memory_is_rejected(self):
        value = request()
        value['memories'][0]['available_at'] = 100
        with self.assertRaises(ValueError):
            recall(value)

    def test_observed_zero_is_distinct_from_missing(self):
        value = request()
        value['query']['cue'] = [None] * 9
        value['query']['events'] = []
        result = recall(value)
        self.assertEqual(result['known_features'], 0)
        value['query']['cue'][0] = '0'
        self.assertEqual(recall(value)['known_features'], 1)

    def test_deny_survives_successful_recall(self):
        from mj_memory_recall import request_digest
        value = request()
        result = recall(value, review={'profile': 'MJ-Memory-Review/0.1.0',
            'request_sha256': request_digest(value), 'verdict': 'DENY'})
        self.assertEqual(result['candidate'], 'memory-a')
        self.assertEqual(result['review_status'], 'DOWNSTREAM_DENY')
        self.assertFalse(result['advisory_ready'])


if __name__ == '__main__':
    unittest.main()
