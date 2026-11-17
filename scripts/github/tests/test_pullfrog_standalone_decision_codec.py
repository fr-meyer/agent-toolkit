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

    def fixture(self, recommendation='implement', reason='actionable_work'):
        answers = {key: dict(type='choice', choice=choice, confidence=-0.5,
                            probabilities={label: 0.2 for label in labels})
                   for key, labels, choice in [('recommendation', codec.RECOMMENDATIONS, recommendation),
                                               ('reason', codec.REASONS, reason)]}
        return dict(status='ok', result=dict(model='kev-latest', answers=answers,
                    usage={'inputTokens': 25.5}), provenance=dict(providerId='typesafe',
                    rubricVersion=decision.RUBRIC_VERSION, runtimeGeneration='opaque-generation'))

    def trusted(self, outcome):
        return dict(source_pin=codec.SOURCE_PIN, agent_id=codec.AGENT_ID, purpose=codec.PURPOSE,
                    payload_digest=contract.digest(self.payload), outcome_digest=contract.digest(outcome))

    def decode_runtime(self, outcome):
        return codec.decode(self.payload, outcome, trusted_receipt=self.trusted(outcome), **self.authority)

    def test_typed_semantics_full_receipt(self):
        for recommendation, reason in [('implement', 'actionable_work'), ('skip', 'no_change'),
                                      ('needs_review', 'uncertain'), ('needs_review', 'unsafe'),
                                      ('needs_review', 'missing_evidence'), ('needs_review', 'out_of_scope')]:
            outcome = self.fixture(recommendation, reason)
            response, receipt = self.decode_runtime(outcome)
            self.assertEqual(response['outcome'], recommendation)
            self.assertEqual(receipt['runtime_outcome'], outcome)
            self.assertTrue(receipt['usage_known'])
            self.assertFalse(receipt['cost_known'])
            accepted = decision.evaluate(self.payload['request'], self.payload['evidence'],
                                        provider=lambda _: response, now=150)
            self.assertEqual(accepted['status'], 'ok')
            receipt['runtime_outcome']['result']['model'] = 'changed'
            self.assertEqual(outcome['result']['model'], 'kev-latest')

    def test_operational_reasons(self):
        for reason in codec.UNAVAILABLE:
            outcome = dict(status='unavailable', reason=reason)
            response, receipt = self.decode_runtime(outcome)
            self.assertEqual(response['status'], 'unavailable')
            self.assertNotIn('outcome', response)
            self.assertEqual(receipt['runtime_outcome'], outcome)

    def test_result_validation(self):
        mutations = [lambda o: o.update(extra=True),
            lambda o: o['provenance'].update(rubricVersion='wrong'),
            lambda o: o['provenance'].pop('runtimeGeneration'),
            lambda o: o['result'].update(model='https://bad endpoint'),
            lambda o: o['result']['usage'].update(cost=0),
            lambda o: o['result']['usage'].update(inputTokens=-1),
            lambda o: o['result']['usage'].update(inputTokens=True),
            lambda o: o['result']['answers']['reason'].update(choice='no_change'),
            lambda o: o['result']['answers']['reason'].update(type='boolean'),
            lambda o: o['result']['answers']['reason'].update(explanation='not allowed'),
            lambda o: o['result']['answers']['reason']['probabilities'].update(unsafe=1.01),
            lambda o: o['result']['answers']['reason']['probabilities'].update(unsafe=float('inf')),
            lambda o: o['result']['answers']['reason'].update(confidence=float('nan')),
            lambda o: o['result']['answers']['reason'].update(probabilities={k: 0 for k in codec.REASONS}),
            lambda o: o['result']['answers'].pop('reason')]
        for index, mutate in enumerate(mutations):
            outcome = self.fixture()
            mutate(outcome)
            with self.subTest(index=index), self.assertRaises(codec.CodecError):
                self.decode_runtime(outcome)

    def test_correlation_unknown_usage_bounds(self):
        outcome = self.fixture()
        for key in ('source_pin', 'agent_id', 'purpose', 'payload_digest', 'outcome_digest'):
            trusted = self.trusted(outcome)
            trusted[key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(codec.CodecError):
                codec.decode(self.payload, outcome, trusted_receipt=trusted, **self.authority)
        del outcome['result']['usage']
        _, receipt = self.decode_runtime(outcome)
        self.assertNotIn('usage', receipt['runtime_outcome']['result'])
        self.assertFalse(receipt['usage_known'])
        outcome['provenance']['runtimeGeneration'] = 'x' * 33000
        with self.assertRaises(codec.CodecError):
            self.decode_runtime(outcome)

if __name__ == '__main__':
    unittest.main()
