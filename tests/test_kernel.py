"""Native lifecycle and evidence-qualified, non-installing model assessment."""
from copy import deepcopy
from decimal import Decimal
import unittest

from mj_memory_recall import engine
from mj_memory_recall.kernel import assess_update, transition


def proposal(count=30):
    baseline = {'model_sha256': '1' * 64, 'program_profile_sha256': '3' * 64,
                'game_plan_sha256': '4' * 64, 'film_evidence_sha256': '5' * 64}
    candidate = dict(baseline, model_sha256='2' * 64)
    signals = [{'id': 'signal-' + str(i), 'receipt_ref': 'receipt-' + str(i),
        'namespace': 'project.alpha', 'observed_at': 10 + i * 2, 'available_at': 11 + i * 2,
        'provenance': 'OBSERVED', 'classified': True, 'compatible': True,
        'domain_retention_qualified': True} for i in range(count)]
    validation = [{'id': 'validation-' + str(i), 'receipt_ref': 'validation-receipt-' + str(i),
        'namespace': 'project.alpha', 'observed_at': 200 + i * 2, 'available_at': 201 + i * 2,
        'provenance': 'OBSERVED', 'target': '1', 'prior_prediction': '0.5', 'candidate_prediction': '0.9'}
        for i in range(3)]
    return {'profile': 'MJ-Memory-Update/0.1.0', 'id': 'candidate-request', 'namespace': 'project.alpha',
            'as_of': 500, 'baseline': baseline, 'candidate': candidate, 'signals': signals, 'validation': validation}


def review(request, verdict='PASS'):
    return {'profile': 'MJ-Memory-Update-Review/0.1.0', 'request_sha256': engine.request_digest(request), 'verdict': verdict}


class KernelContracts(unittest.TestCase):
    def test_native_lifecycle_requires_checkpoint_and_never_reuses_uncleared_generation(self):
        state = {'stage': 'ACTIVE', 'generation': 0}
        for illegal in ('SEAL', 'CHECKPOINT', 'DETACH', 'RECLAIM', 'ACTIVATE'):
            with self.subTest(illegal=illegal), self.assertRaises(ValueError):
                transition(state, illegal, checkpoint_valid=True)
        state = transition(state, 'QUIESCE')['state']
        state = transition(state, 'SEAL')['state']
        with self.assertRaises(ValueError):
            transition(state, 'CHECKPOINT')
        state = transition(state, 'CHECKPOINT', checkpoint_valid=True)['state']
        state = transition(state, 'DETACH', checkpoint_valid=True)['state']
        state = transition(state, 'RECLAIM', checkpoint_valid=True)['state']
        self.assertEqual(transition(state, 'ACTIVATE', checkpoint_valid=True)['state']['generation'], 1)

    def test_qualified_update_is_only_a_hashed_proposal_with_native_brier_loss(self):
        value = proposal()
        actual = assess_update(value, review=review(value))
        self.assertTrue(actual['promoted'])
        self.assertEqual(actual['qualified_signals'], 30)
        self.assertEqual(Decimal(actual['prior_loss']), Decimal('0.25'))
        self.assertEqual(Decimal(actual['candidate_loss']), Decimal('0.01'))
        self.assertEqual(actual['candidate_sha256'], '2' * 64)
        self.assertFalse(actual['model_installed'])
        self.assertFalse(actual['program_profile_changed'])

    def test_one_outcome_and_unqualified_domain_signals_cannot_train(self):
        cases = [proposal(1), proposal(29)]
        for field, value in [('provenance', 'SYNTHETIC'), ('provenance', 'COACH_PROFILE'),
                ('provenance', 'FILM'), ('classified', False), ('compatible', False),
                ('domain_retention_qualified', False)]:
            changed = proposal()
            changed['signals'][0][field] = value
            cases.append(changed)
        for changed in cases:
            with self.subTest(signal=changed['signals'][0], count=len(changed['signals'])):
                self.assertFalse(assess_update(changed, review=review(changed))['promoted'])

    def test_temporally_later_disjoint_validation_and_first_observation_are_required(self):
        cases = []
        for field, value in [('id', 'signal-0'), ('receipt_ref', 'receipt-0'),
                            ('observed_at', 1), ('available_at', 500), ('provenance', 'SYNTHETIC')]:
            changed = proposal()
            changed['validation'][0][field] = value
            cases.append(changed)
        changed = proposal()
        changed['validation'].pop()
        cases.append(changed)
        changed = proposal()
        changed['signals'][1]['receipt_ref'] = changed['signals'][0]['receipt_ref']
        cases.append(changed)
        for changed in cases:
            with self.subTest(changed=changed['validation'][0]):
                self.assertFalse(assess_update(changed, review=review(changed))['promoted'])

    def test_missing_review_deny_and_wrong_binding_cannot_promote(self):
        value = proposal()
        self.assertFalse(assess_update(value)['promoted'])
        self.assertEqual(assess_update(value, review=review(value, 'DENY'))['reason'], 'DOWNSTREAM_DENY')
        wrong = review(value)
        value['candidate']['model_sha256'] = '6' * 64
        with self.assertRaises(ValueError):
            assess_update(value, review=wrong)

    def test_tied_or_worse_loss_and_any_protected_profile_rewrite_are_held(self):
        for prediction in ('0.5', '0.1'):
            value = proposal()
            for item in value['validation']:
                item['candidate_prediction'] = prediction
            self.assertEqual(assess_update(value, review=review(value))['reason'], 'LOSS_NOT_IMPROVED')
        for field in ('program_profile_sha256', 'game_plan_sha256', 'film_evidence_sha256'):
            value = proposal()
            value['candidate'][field] = 'f' * 64
            self.assertEqual(assess_update(value, review=review(value))['reason'], 'PROFILE_REWRITE_FORBIDDEN')

    def test_maximum_update_request_fits_unchanged_runtime_limits(self):
        value = proposal(64)
        for i in range(3, 16):
            item = deepcopy(value['validation'][0])
            item.update(id='validation-' + str(i), receipt_ref='validation-receipt-' + str(i),
                        observed_at=200+i*2, available_at=201+i*2)
            value['validation'].append(item)
        self.assertTrue(assess_update(value, review=review(value))['promoted'])


if __name__ == '__main__':
    unittest.main()
