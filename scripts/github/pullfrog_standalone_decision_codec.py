"""Pure documented Decision batch codec. No dispatch or runtime qualification.

Full runtime result decoding is deliberately unavailable until the adapter has
an exact trusted SDK result/provenance contract, not just illustrative docs.
"""
import copy
from concurrent.futures import CancelledError
import pullfrog_standalone_contract as contract
import pullfrog_standalone_decision as decision

AGENT_ID = 'franck'
PURPOSE = 'pullfrog.standalone.recommendation'
RECOMMENDATIONS = {
    'implement': 'Concrete actionable work within original scope and budget.',
    'skip': 'No justified change; not readiness or review certification.',
    'needs_review': 'Uncertainty, missing evidence, unsafe or out-of-scope work.',
}
REASONS = {
    'actionable_work': 'Concrete actionable authorized work.',
    'no_change': 'No justified change.',
    'uncertain': 'Uncertain or conflicting evidence.',
    'missing_evidence': 'Required evidence absent.',
    'out_of_scope': 'Work exceeds original scope or budget.',
    'unsafe': 'Unsafe work.',
}

class CodecError(ValueError):
    pass


def _require(condition):
    if not condition:
        raise CodecError('invalid_codec_contract')


def encode(payload, *, now, deadline, destination_authorized=False, cancelled=False):
    """Return documented (batch, options), never invoke a runtime.

    Deadline and now are integer epoch seconds. The trusted adapter must attach
    its live cancellation signal and recheck destination authority at dispatch.
    Owning agent is policy-fixed; there is no caller model, endpoint or agent.
    """
    if cancelled:
        raise CancelledError()
    _require(destination_authorized is True)
    _require(type(now) is int and type(deadline) is int and now < deadline <= now + 30)
    try:
        decision._bounded(payload, decision.MAX_EVIDENCE_BYTES)
        _require(type(payload) is dict and set(payload) == {
            'schema', 'binding', 'evidence_digest', 'rubric_version', 'rubric', 'request', 'evidence'})
        _require(payload['schema'] == decision.INPUT_SCHEMA)
        _require(payload['rubric_version'] == decision.RUBRIC_VERSION and payload['rubric'] == decision.RUBRIC)
        contract.validate_request(payload['request'], now=now)
        _require(deadline <= payload['request']['expires_at'])
        contract.validate_binding(payload['binding'], payload['request'], head_sha=payload['binding']['head_sha'])
        decision._strict_binding(payload['evidence']['binding'], payload['binding'])
        body = {k: v for k, v in payload['evidence'].items() if k != 'evidence_digest'}
        _require(payload['evidence_digest'] == contract.digest(body))
        _require(payload['evidence'].get('evidence_digest', payload['evidence_digest']) == payload['evidence_digest'])
    except (KeyError, TypeError, ValueError, decision._Invalid, RecursionError) as exc:
        raise CodecError('invalid_codec_contract') from exc
    questions = {key: {'type': 'choice', 'instructions': decision.RUBRIC, 'criteria': criteria}
                 for key, criteria in [('recommendation', RECOMMENDATIONS), ('reason', REASONS)]}
    return ({'state': copy.deepcopy(payload), 'questions': copy.deepcopy(questions)},
            {'agentId': AGENT_ID, 'purpose': PURPOSE, 'rubricVersion': decision.RUBRIC_VERSION,
             'timeoutMs': (deadline - now) * 1000})


def decode(payload, outcome=None, **authority):
    """Fail closed pending exact trusted runtime result/provenance type.

    Do not invent provenance fields from docs, treat a model alias as checkpoint
    identity, discard usage/cost, or manufacture a semantic answer on failure.
    No supplied result is accepted as trusted. Absence remains unavailable.
    """
    encode(payload, **authority)
    if outcome is not None:
        raise CodecError('trusted_runtime_result_contract_unavailable')
    response = {k: copy.deepcopy(payload[k]) for k in ('binding', 'evidence_digest', 'rubric_version')}
    response.update(schema=decision.PROVIDER_SCHEMA, status='unavailable',
                    provenance={'provider': 'openclaw', 'model': 'unavailable'})
    return response, {'runtime_outcome': None, 'usage_known': False, 'cost_known': False}
