"""Pure documented Decision batch codec. No dispatch or runtime qualification.

Targets pinned source API only, not installed or deployed runtime readiness.
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


# Read-only source: src/decisions/{types,validation,runtime,runtime.test-support}.ts
# and src/plugin-sdk/decisions.ts, exact git object below.
SOURCE_PIN = '30786562e236aab6a924981c62aa61b920132c76'
MAX_RECEIPT_BYTES = 32768
UNAVAILABLE = {'credentials-unavailable', 'authentication', 'rate-limited', 'transport',
               'unsupported-input', 'invalid-response', 'disabled', 'not-configured',
               'retiring', 'overloaded', 'circuit-open', 'deadline'}


def _finite_json(value):
    import json
    import math
    nodes = 0
    def visit(v, depth=0):
        nonlocal nodes
        nodes += 1
        _require(nodes <= 4000 and depth <= 12)
        if v is None or type(v) in (bool, str, int):
            return
        if type(v) is float:
            _require(math.isfinite(v))
            return
        _require(type(v) in (dict, list) and len(v) <= 200)
        if type(v) is dict:
            _require(all(type(k) is str and len(k) <= 128 for k in v))
        for child in v.values() if type(v) is dict else v:
            visit(child, depth + 1)
    visit(value)
    _require(len(json.dumps(value, allow_nan=False).encode()) <= MAX_RECEIPT_BYTES)


def _number(v, probability=False):
    import math
    return (type(v) in (int, float) and math.isfinite(v)
            and (not probability or 0 <= v <= 1))


def decode(payload, outcome=None, *, trusted_receipt=None, **authority):
    """Decode pinned DecisionOutcome, not installed-runtime readiness.

    trusted_receipt is adapter-owned correlation metadata, NOT OpenClaw wire
    schema or caller evidence. Only the trusted adapter may create it after its
    live owned call, binding full payload/outcome hashes. Python objects cannot
    authenticate their supplier. No caller model/provider/agent override exists.
    """
    encode(payload, **authority)
    response = {k: copy.deepcopy(payload[k]) for k in ('binding', 'evidence_digest', 'rubric_version')}
    response.update(schema=decision.PROVIDER_SCHEMA, status='unavailable',
                    provenance={'provider': 'openclaw', 'model': 'unavailable'})
    if outcome is None:
        _require(trusted_receipt is None)
        return response, {'runtime_outcome': None, 'usage_known': False, 'cost_known': False}
    _finite_json(outcome)
    _require(type(trusted_receipt) is dict and set(trusted_receipt) == {
        'source_pin', 'agent_id', 'purpose', 'payload_digest', 'outcome_digest'})
    _require(trusted_receipt == {
        'source_pin': SOURCE_PIN, 'agent_id': AGENT_ID, 'purpose': PURPOSE,
        'payload_digest': contract.digest(payload), 'outcome_digest': contract.digest(outcome)})
    _require(type(outcome) is dict)
    receipt = {'runtime_outcome': copy.deepcopy(outcome),
               'trusted_receipt': copy.deepcopy(trusted_receipt), 'cost_known': False,
               'usage_known': False}
    if outcome.get('status') == 'unavailable':
        _require(set(outcome) == {'status', 'reason'} and type(outcome['reason']) is str
                 and outcome['reason'] in UNAVAILABLE)
        _finite_json(receipt)
        return response, receipt
    _require(set(outcome) == {'status', 'result', 'provenance'} and outcome['status'] == 'ok')
    provenance = outcome['provenance']
    _require(type(provenance) is dict and set(provenance) == {
        'providerId', 'rubricVersion', 'runtimeGeneration'})
    _require(provenance['rubricVersion'] == decision.RUBRIC_VERSION)
    _require(type(provenance['providerId']) is str and decision.IDENTIFIER.fullmatch(provenance['providerId']))
    _require(type(provenance['runtimeGeneration']) is str and 0 < len(provenance['runtimeGeneration']) <= 1024)
    result = outcome['result']
    _require(type(result) is dict and {'model', 'answers'} <= set(result)
             and set(result) <= {'model', 'answers', 'usage'})
    # Reject SDK names outside the existing provider-response identifier subset;
    # never rewrite them or infer a checkpoint from an alias.
    _require(type(result['model']) is str and decision.IDENTIFIER.fullmatch(result['model']))
    if 'usage' in result:
        usage = result['usage']
        _require(type(usage) is dict and set(usage) <= {'inputTokens', 'outputTokens'})
        _require(all(_number(n) and n >= 0 for n in usage.values()))
        receipt['usage_known'] = bool(usage)
    answers = result['answers']
    _require(type(answers) is dict and set(answers) == {'recommendation', 'reason'})
    choices = {}
    for key, labels in [('recommendation', RECOMMENDATIONS), ('reason', REASONS)]:
        answer = answers[key]
        _require(type(answer) is dict and {'type', 'choice', 'probabilities'} <= set(answer)
                 and set(answer) <= {'type', 'choice', 'probabilities', 'confidence'})
        _require(answer['type'] == 'choice' and type(answer['choice']) is str and answer['choice'] in labels)
        ps = answer['probabilities']
        _require(type(ps) is dict and set(ps) == set(labels))
        _require(all(_number(p, True) for p in ps.values()) and any(p > 0 for p in ps.values()))
        if 'confidence' in answer:
            _require(_number(answer['confidence']))
        choices[key] = answer['choice']
    recommendation, reason = choices['recommendation'], choices['reason']
    _require((recommendation == 'implement' and reason == 'actionable_work')
             or (recommendation == 'skip' and reason == 'no_change')
             or (recommendation == 'needs_review' and reason not in {'actionable_work', 'no_change'}))
    response.update(status='ok', outcome=recommendation, reason=reason,
                    provenance={'provider': provenance['providerId'], 'model': result['model']})
    _finite_json(receipt)
    return response, receipt
