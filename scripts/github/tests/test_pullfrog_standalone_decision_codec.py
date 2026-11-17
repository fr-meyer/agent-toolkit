"""Offline fixtures, not real runtime qualification."""
import copy
import unittest
from concurrent.futures import CancelledError
from test_pullfrog_standalone_decision import request
import pullfrog_standalone_contract as contract
import pullfrog_standalone_decision as decision
import pullfrog_standalone_decision_codec as codec

class CodecTests(unittest.TestCase):
    def setUp(self):
        r = request()
        evidence = {'binding': contract.binding(r), 'context': 'bounded'}
        self.payload = dict(schema=decision.INPUT_SCHEMA, binding=contract.binding(r),
                            evidence_digest=contract.digest(evidence), evidence=evidence,
                            request=r, rubric=decision.RUBRIC, rubric_version=decision.RUBRIC_VERSION)
        self.authority = dict(now=150, deadline=170, destination_authorized=True)

    def test_documented_batch(self):
        batch, options = codec.encode(self.payload, **self.authority)
        self.assertEqual(set(batch), {'state', 'questions'})
        self.assertEqual(set(batch['questions']), {'recommendation', 'reason'})
        for q in batch['questions'].values():
            self.assertEqual(set(q), {'type', 'instructions', 'criteria'})
            self.assertEqual(q['type'], 'choice')
        self.assertEqual(options['agentId'], 'franck')
        self.assertEqual(options['timeoutMs'], 20000)
        batch['state']['request']['budget']['max_cost_microusd'] = 999
        self.assertEqual(self.payload['request']['budget']['max_cost_microusd'], 0)

    def test_authority_deadline_cancellation(self):
        for change in ({'destination_authorized': False}, {'deadline': 150},
                       {'deadline': 181}, {'now': True}, {'now': 201, 'deadline': 210}):
            with self.subTest(change=change), self.assertRaises(codec.CodecError):
                codec.encode(self.payload, **(self.authority | change))
        with self.assertRaises(CancelledError):
            codec.encode(self.payload, **self.authority, cancelled=True)

    def test_missing_extra_mismatch_bounds(self):
        for key, value in [('schema', 'wrong'), ('rubric', 'wrong'),
                           ('evidence_digest', '0' * 64), ('agentId', 'other')]:
            p = copy.deepcopy(self.payload)
            p[key] = value
            with self.subTest(key=key), self.assertRaises(codec.CodecError):
                codec.encode(p, **self.authority)
        for value in (float('nan'), float('inf'), 'x' * 65537):
            p = copy.deepcopy(self.payload)
            p['evidence']['context'] = value
            with self.assertRaises(codec.CodecError):
                codec.encode(p, **self.authority)
        p = copy.deepcopy(self.payload)
        del p['rubric']
        with self.assertRaises(codec.CodecError):
            codec.encode(p, **self.authority)

    def test_unavailable_compatible_not_semantic(self):
        response, receipt = codec.decode(self.payload, **self.authority)
        self.assertEqual(response['status'], 'unavailable')
        self.assertNotIn('outcome', response)
        self.assertFalse(receipt['usage_known'])
        self.assertFalse(receipt['cost_known'])
        r = self.payload['request']
        result = decision.evaluate(r, self.payload['evidence'], provider=lambda _: response, now=150)
        self.assertEqual(result['status'], 'unavailable')

    def test_no_untrusted_runtime_answer_accepted(self):
        for outcome in ({'status': 'ok', 'result': {'answers': {}}},
                        {'status': 'unavailable', 'reason': 'deadline'},
                        {'probabilities': {'implement': 1.01}},
                        {'usage': {'cost': float('nan')}}):
            with self.assertRaises(codec.CodecError):
                codec.decode(self.payload, outcome, **self.authority)

if __name__ == '__main__':
    unittest.main()
