#!/usr/bin/env python3
"""Read-only host qualification and fail-closed live worker admission.

No qualified execution primitive is implemented. Binary presence, subscription
login, environment filtering and the legacy fork runner are not qualification.
Never launches commands, consumes reservations or changes registries.
"""
import os
import shutil
from pathlib import Path

import pullfrog_standalone_execution_profile as profiles

BINARIES = ('codex', 'docker', 'podman', 'bwrap', 'nsjail', 'firejail',
            'systemd-run', 'prlimit', 'timeout')
UNVERIFIED = (
    'immutable_cli_image_build_identity_unverified',
    'exact_model_resolution_unverified',
    'subscription_only_no_billable_fallback_unverified',
    'independent_quota_and_zero_incremental_cost_hard_stop_unverified',
    'cpu_memory_pid_disk_time_hard_limits_unverified',
    'network_and_credential_boundary_unverified',
    'trusted_recipe_and_destination_privacy_unverified',
    'atomic_durable_consumed_reservation_unverified',
    'cancellation_cleanup_remote_quiescence_unverified',
    'independent_usage_reconciliation_unverified',
    'qualified_live_adapter_not_implemented',
)


def inventory():
    """Bounded status only. Never inspect env, auth, process args or run a CLI."""
    root = Path('/sys/fs/cgroup')
    return {
        'binaries_present': {name: shutil.which(name) is not None for name in BINARIES},
        'cgroup_v2_present': (root / 'cgroup.controllers').is_file(),
        'cgroup_subtree_writable': os.access(root / 'cgroup.subtree_control', os.W_OK),
    }


def qualification():
    """Actual local negative check, not a caller-attested capability gate.

    No evidence/flags/registry argument. Even all binaries need an independently
    qualified fixed adapter retaining profiles.CAPABILITIES, authenticated exact
    context and the atomic consumed-claim contract. Availability is not authority.
    """
    observed = inventory()
    blockers = list(UNVERIFIED)
    present = observed['binaries_present']
    if not present['codex']:
        blockers.insert(0, 'codex_binary_unavailable')
    if not any(present[k] for k in ('docker', 'podman', 'bwrap', 'nsjail', 'firejail')):
        blockers.insert(0, 'isolated_runtime_binary_unavailable')
    if not observed['cgroup_v2_present'] or not observed['cgroup_subtree_writable']:
        blockers.insert(0, 'delegated_cgroup_limits_unavailable')
    return {'schema': 'pullfrog-standalone-runtime-qualification.v1',
            'status': 'unavailable', 'live_execution_allowed': False,
            'observed': observed, 'blockers': blockers,
            'required_capabilities': sorted(profiles.CAPABILITIES)}


def admit(request, plan, profile, *, current_head_sha, now, cancelled=False):
    """Refuse before new reservation/effects; never refund or reset prior usage.

    reservation_consumed=None means durable state was not inspected. The caller
    may already hold a consumed reservation: refusal must not remint it.
    Cancellation prevents admission, not proof an existing job stopped.
    """
    report = qualification()
    reason = 'runtime_unqualified'
    try:
        profiles.context(request, plan, profile,
                         current_head_sha=current_head_sha, now=now)
    except Exception:
        reason = 'profile_or_binding_rejected'
    else:
        if cancelled:
            reason = 'cancelled_before_admission'
    return {'schema': 'pullfrog-standalone-runtime-admission.v1',
            'status': 'unavailable', 'reason': reason,
            'qualification': report, 'live_execution_allowed': False,
            'reservation_consumed': None, 'new_reservation_consumed': False,
            'effects_started': False, 'cleanup_verified': False,
            'cost_microusd': None, 'usage': None,
            'retry_allowed': False, 'reconciliation_required': True,
            'merge_allowed': False}


if __name__ == '__main__':
    import json
    print(json.dumps(qualification(), sort_keys=True))
    raise SystemExit(2)
