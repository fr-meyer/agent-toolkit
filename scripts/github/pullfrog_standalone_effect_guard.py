"""Trusted host-owned live policy/deadline guard, never model/event authority."""
import inspect
import math
import pullfrog_standalone_admission as admission
import pullfrog_standalone_contract as k


class EffectGuard:
    def __init__(self, request, state, binding, *, policy_loader, now, clock):
        self.request, self.state, self.binding = request, state, binding
        self.policy_loader, self.clock = policy_loader, clock
        self.start = clock()
        self.now = now
        self.deadline = min(request['expires_at'], state['started_at'] + request['budget']['max_seconds'])
        self.last = 0

    def elapsed(self):
        value = self.clock() - self.start
        if not math.isfinite(value) or value < self.last:
            raise k.ContractError('effect_clock_invalid')
        self.last = value
        return value

    def check(self):
        policy = self.policy_loader()
        if not admission._authorized(self.request['initiator'], policy, self.request):
            raise k.ContractError('authority_revoked')
        if (self.binding != k.binding(self.request, head_sha=self.state['current_head'])
                or self.state['terminal'] or self.state['seconds'] >= self.request['budget']['max_seconds']
                or self.state['attempts'] > self.request['budget']['max_attempts']
                or self.state['cost_microusd'] > self.request['budget']['max_cost_microusd']):
            raise k.ContractError('effect_binding_or_budget_invalid')
        left = self.deadline - self.now - self.elapsed()
        if left <= 0:
            raise k.ContractError('effect_deadline_exhausted')
        return min(30, left)


class BoundedClient:
    def __init__(self, client, guard):
        self.client, self.guard = client, guard
        # Explicit supported interface only; no TypeError fallback that might
        # repeat a request or silently use the old constant timeout.
        for name in ('get', 'post', 'graphql'):
            parameters = inspect.signature(getattr(client, name)).parameters.values()
            if not any(p.kind == p.VAR_KEYWORD for p in parameters):
                names = {p.name for p in parameters}
                if not {'timeout', 'before_send'} <= names:
                    raise k.ContractError('bounded_github_transport_required')

    def _call(self, name, *args):
        timeout = self.guard.check()
        result = getattr(self.client, name)(*args, timeout=timeout, before_send=self.guard.check)
        self.guard.check()
        return result

    def get(self, path):
        return self._call('get', path)

    def post(self, path, payload):
        return self._call('post', path, payload)

    def graphql(self, query, variables):
        return self._call('graphql', query, variables)
