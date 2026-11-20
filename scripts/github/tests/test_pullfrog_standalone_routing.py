"""Offline boundary regressions, not provider-quality or live acceptance."""
import copy
from concurrent.futures import CancelledError
import test_pullfrog_standalone_controller as fixtures
import pullfrog_standalone_controller as ctl
import pullfrog_standalone_contract as contract
import pullfrog_standalone_decision as decision
import pullfrog_standalone_decision_codec as codec


import unittest


class RoutingTests(unittest.TestCase):
    setUp = fixtures.ControllerTests.setUp
    load = fixtures.ControllerTests.load
    admit = fixtures.ControllerTests.admit
    def route(self, digest, provider=None, clock=lambda: 0.0):
        return ctl.route(self.journal, self.policy, self.context, self.execution,
                         self.destination, expected_digest=digest, now=111,
                         provider=provider, clock=clock)

    def provider(self, action):
        def respond(payload):
            # Exercise actual codec before returning an isolated provider answer.
            batch, options = codec.encode(payload, now=111, deadline=120, destination_authorized=True)
            self.assertEqual(set(batch['questions']), {'next_action'})
            self.assertEqual(options['agentId'], 'franck')
            value = {k: copy.deepcopy(payload[k]) for k in ('binding', 'evidence_digest', 'rubric_version')}
            value.update(schema=decision.V2_PROVIDER_SCHEMA, status='ok', next_action=action,
                         provenance={'provider': 'isolated', 'model': 'boundary'})
            return value
        return respond

    def test_rejected_handler_never_creates_worker(self):
        first = self.admit()
        result = self.route(first['journal_digest'], self.provider('retry_ci'))
        self.assertEqual(result['output']['decision']['status'], 'error')
        self.assertNotIn('worker_plan', self.load()['artifacts'])
        self.assertTrue(self.load()['state']['terminal'])

    def test_explicit_bridge_produces_existing_guarded_worker(self):
        first = self.admit()
        result = self.route(first['journal_digest'], self.provider('implement_fix'))
        self.assertEqual(result['output']['worker_plan']['attempt'], 1)
        self.assertEqual(self.load()['phase'], 'worker_ready')
        with self.assertRaises(contract.ContractError):
            self.route(result['journal_digest'], self.provider('implement_fix'))
        self.assertEqual(self.load()['state']['attempts'], 1)

    def test_wait_skips_provider_and_has_no_polling_effect(self):
        self.context['dependency_running'] = True
        first = self.admit()
        result = self.route(first['journal_digest'], lambda p: self.fail('facts must not invoke model'))
        self.assertEqual(self.load()['phase'], 'waiting_dependency')
        self.assertIsNone(result['output']['worker_plan'])
        self.assertEqual(self.load()['state']['attempts'], 1)

    def test_revoked_authority_precedes_provider(self):
        first = self.admit()
        self.policy['initiators'] = []
        with self.assertRaisesRegex(contract.ContractError, 'authority_revoked'):
            self.route(first['journal_digest'], lambda p: self.fail('unauthorized model invocation'))

    def test_model_time_cannot_escape_original_deadline(self):
        first = self.admit()
        ticks = iter([0.0, 0.0, 2000.0])
        result = self.route(first['journal_digest'], self.provider('implement_fix'), clock=lambda: next(ticks))
        self.assertIsNone(result['output']['worker_plan'])
        self.assertTrue(self.load()['state']['terminal'])

    def test_crash_holds_exact_call_across_restart(self):
        first = self.admit()
        def crash(p):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.route(first['journal_digest'], crash)
        prior = self.load()
        self.assertEqual(prior['phase'], 'decision_started')
        with self.assertRaises(contract.ContractError):
            self.route(contract.digest(prior), lambda p: self.fail('duplicate invocation'))

    def test_no_action_does_not_claim_ready_or_clear_findings(self):
        first = self.admit()
        result = self.route(first['journal_digest'], self.provider('no_action'))
        self.assertFalse(result['output']['merge_allowed'])
        self.assertEqual(self.load()['state']['reason'], 'decision_no_action')
        self.assertNotEqual(self.load()['state']['reason'], 'ready_for_human')

    def test_refusal_is_not_no_action(self):
        first = self.admit()
        def refuse(payload):
            result = self.provider('no_action')(payload)
            result.pop('next_action')
            result['status'] = 'refused'
            return result
        result = self.route(first['journal_digest'], refuse)
        self.assertEqual(result['output']['decision']['status'], 'refused')
        self.assertEqual(self.load()['state']['reason'], 'decision_refused')

    def test_v2_decode_requires_one_choice_and_preserves_binding(self):
        first = self.admit()
        def roundtrip(payload):
            actions = payload['eligible_actions']
            outcome = {'status': 'ok', 'result': {'model': 'boundary', 'answers': {
                'next_action': {'type': 'choice', 'choice': 'ask_human',
                                'probabilities': {a: 1 if a == 'ask_human' else 0 for a in actions}}}},
                'provenance': {'providerId': 'isolated', 'rubricVersion': decision.V2_RUBRIC_VERSION,
                               'runtimeGeneration': 'offline'}}
            trusted = dict(source_pin=codec.SOURCE_PIN, agent_id='franck', purpose=codec.PURPOSE,
                           payload_digest=contract.digest(payload), outcome_digest=contract.digest(outcome))
            decoded, _ = codec.decode(payload, outcome, trusted_receipt=trusted,
                                      now=111, deadline=120, destination_authorized=True)
            return decoded
        result = self.route(first['journal_digest'], roundtrip)
        self.assertEqual(result['output']['decision']['next_action'], 'ask_human')
        self.assertIsNone(result['output']['worker_plan'])
        self.assertEqual(self.load()['state']['reason'], 'decision_ask_human')

    def test_lock_elapsed_prevents_model_invocation(self):
        first = self.admit()
        ticks = iter([0.0, 2000.0, 2000.0])
        calls = []
        result = self.route(first['journal_digest'], lambda p: calls.append(p),
                            clock=lambda: next(ticks))
        self.assertEqual(calls, [])
        self.assertIsNone(result['output']['worker_plan'])
        self.assertTrue(self.load()['state']['terminal'])
