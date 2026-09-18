from copy import deepcopy
import unittest

from mj_memory_recall import recall
from test_recall import request


class ForecastTests(unittest.TestCase):
    def test_previous_command_conditions_observed_transition_counts(self):
        value = request()
        for memory in value['memories']:
            memory['trace'] = [{'actor': 'sensor', 'step': step, 'position': None,
                'command': token} for step, token in enumerate(['measure', 'derive', 'measure', 'derive'])]
        result = recall(value)
        self.assertEqual(result['forecast']['command'], 'derive')
        self.assertEqual(result['forecast']['support'], 4)
        self.assertEqual(result['forecast']['node'], 3)
        self.assertFalse(result['model_updated'])
        value['query']['previous_command'] = 'emit'
        self.assertFalse(recall(value)['forecast']['available'])

    def test_missing_commands_and_steps_are_not_bridged(self):
        value = request()
        for memory in value['memories']:
            memory['trace'] = [{'actor': 'sensor', 'step': step, 'position': None,
                'command': token} for step, token in [(0, 'measure'), (2, 'derive'), (3, None), (4, 'emit')]]
        self.assertEqual(recall(value)['forecast']['support'], 0)
