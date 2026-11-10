#!/usr/bin/env python3
"""Synthetic GitHub-hosted pilot; never admits general candidate code or providers.

Local tests mock Docker. The CLI requires an explicitly approved hosted push.
Environment checks are constraints, not cryptographic workflow authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import tempfile

REPOSITORY = "fr-meyer/agent-toolkit"
BRANCH = "refs/heads/feat/c04-provider-free-pilot-20261110"
# Official Python linux/amd64 manifest observed read-only, 2026-11-10. Not qualified.
IMAGE = "docker.io/library/python@sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4"
PROBES = ("baseline", "pids", "oom", "timeout")
DOCKER = "/usr/bin/docker"

FIXTURE = r'''
import errno,json,os,pathlib,socket,subprocess,sys,time
mode=sys.argv[1]
if mode == 'baseline':
    checks={'nonroot':os.getuid()==65534,
            'no_control_socket':not pathlib.Path('/var/run/docker.sock').exists(),
            'no_host_sentinel':not pathlib.Path(sys.argv[2]).exists(),
            'no_credentials':not any(k for k in os.environ if any(s in k.upper() for s in ('TOKEN','SECRET','API_KEY','PASSWORD')))}
    status=pathlib.Path('/proc/self/status').read_text()
    fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
    checks['no_caps']=int(fields.get('CapEff','1').strip(),16)==0
    checks['no_new_privileges']=fields.get('NoNewPrivs','0').strip()=='1'
    try:
        with open('/probe.py','a') as stream:stream.write('# forbidden')
        checks['fixture_readonly']=False
    except OSError as error:
        checks['fixture_readonly']=error.errno==errno.EROFS
    pathlib.Path('/tmp/synthetic-write').write_text('dummy')
    checks['bounded_scratch_writable']=True
    sock=socket.socket();sock.settimeout(1)
    try:
        sock.connect(('1.1.1.1',443));checks['external_network_denied']=False
    except OSError:
        checks['external_network_denied']=True
    finally:sock.close()
    try:
        cg=pathlib.Path('/sys/fs/cgroup')
        quota,period=(cg/'cpu.max').read_text().split()
        checks['cpu_cgroup_bound']=quota!='max' and 0<int(quota)<=int(period)
        checks['memory_cgroup_bound']=int((cg/'memory.max').read_text())==134217728
        checks['pids_cgroup_bound']=int((cg/'pids.max').read_text())==32
    except (OSError,ValueError):
        checks['cgroup_v2_observed']=False
    print(json.dumps({'probe':mode,'checks':checks}),flush=True)
    sys.exit(0 if all(checks.values()) else 1)
elif mode == 'pids':
    children=[];denied=False
    try:
        for _ in range(40):
            try:children.append(subprocess.Popen(['/bin/sleep','8']))
            except OSError as error:
                denied=error.errno==errno.EAGAIN;break
    finally:
        for child in children:child.kill()
        for child in children:child.wait()
    print(json.dumps({'probe':mode,'checks':{'pids_enforced':denied and 0<len(children)<32}}),flush=True)
    sys.exit(0 if denied else 1)
elif mode == 'oom':
    blocks=[]
    for _ in range(20):blocks.append(bytearray(16*1024*1024))
    sys.exit(2)
elif mode == 'timeout':
    time.sleep(60)
else:sys.exit(3)
'''


class PilotError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PilotError(message)


def hosted_context(env, event):
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push", "RUNNER_ENVIRONMENT": "github-hosted",
                "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": BRANCH}
    require(all(env.get(k) == v for k, v in expected.items()), "wrong hosted pilot context")
    sha = env.get("GITHUB_SHA", "")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)) and env.get("GITHUB_WORKFLOW_SHA") == sha,
            "workflow and head identities are not the same immutable commit")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", env.get(key, ""))), "invalid numeric run identity")
    require(1 <= int(env["GITHUB_RUN_ATTEMPT"]) <= 3, "pilot attempt allowance exhausted")
    require(isinstance(event, dict) and event.get("created") is True and event.get("deleted") is False
            and event.get("ref") == BRANCH and event.get("after") == sha, "not the approved branch creation event")
    repository = event.get("repository", {})
    require(repository.get("full_name") == REPOSITORY and repository.get("private") is False,
            "pilot repository is not the public approved repository")
    return {"repository": REPOSITORY, "ref": BRANCH, "head_sha": sha, "workflow_sha": sha,
            "run_id": int(env["GITHUB_RUN_ID"]), "run_attempt": int(env["GITHUB_RUN_ATTEMPT"]),
            "runner_image_os": env.get("ImageOS", "unknown"), "runner_image_version": env.get("ImageVersion", "unknown")}


def create_command(identity, probe, fixture):
    require(bool(re.fullmatch(r"[1-9][0-9]{0,19}-[1-3]", identity)) and probe in PROBES, "invalid fixed pilot selection")
    fixture = Path(fixture)
    require(fixture.is_absolute() and fixture.name == "probe.py" and "," not in str(fixture)
            and chr(10) not in str(fixture), "invalid synthetic fixture mount")
    return ["create", "--name", "c04-pilot-" + identity + "-" + probe, "--label", "c04-pilot=" + identity,
            "--read-only", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user=65534:65534", "--cpus=1", "--memory=128m", "--memory-swap=128m", "--pids-limit=32",
            "--ipc=none", "--ulimit=nofile=64:64", "--ulimit=core=0:0",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m", "--log-opt=max-size=64k", "--log-opt=max-file=1",
            "--mount", "type=bind,src=" + str(fixture) + ",dst=/probe.py,readonly",
            IMAGE, "python3", "-I", "-B", "/probe.py", probe, str(fixture.parent / "host-only-sentinel")]


def validate_inspection(data, identity, fixture):
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    require(config.get("Image") == IMAGE and config.get("User") == "65534:65534"
            and config.get("Labels", {}).get("c04-pilot") == identity, "wrong inspected image/user/lease identity")
    allowed_env = {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"}
    require(all(isinstance(e, str) and e.split("=", 1)[0] in allowed_env for e in config.get("Env", [])),
            "unapproved container environment")
    exact = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
             "NanoCpus": 1000000000, "Memory": 134217728, "MemorySwap": 134217728,
             "PidsLimit": 32, "IpcMode": "none", "PidMode": ""}
    require(all(host.get(k) == v for k, v in exact.items()), "inspected isolation/resource policy differs")
    require(host.get("CapDrop") == ["ALL"] and not host.get("CapAdd")
            and host.get("SecurityOpt") in (["no-new-privileges"], ["no-new-privileges=true"]), "capability policy differs")
    require(not any(host.get(k) for k in ("Binds", "Devices", "DeviceRequests", "VolumesFrom", "PortBindings")),
            "unapproved host/device/port exposure")
    require(host.get("Tmpfs") == {"/tmp": "rw,noexec,nosuid,nodev,size=16m"}, "scratch policy differs")
    mounts = data.get("Mounts", [])
    binds = [m for m in mounts if m.get("Type") == "bind"]
    require(len(binds) == 1 and binds[0].get("Source") == str(fixture)
            and binds[0].get("Destination") == "/probe.py" and binds[0].get("RW") is False, "fixture mount differs")
    require(all(m in binds or (m.get("Type") == "tmpfs" and m.get("Destination") == "/tmp") for m in mounts),
            "unapproved mount")


def make_receipt(context, probes, cleanup_verified):
    good = (len(probes) == len(PROBES) and {r.get("probe") for r in probes} == set(PROBES)
            and all(r.get("passed") is True for r in probes) and cleanup_verified is True)
    return {"schema_version": "c04-synthetic-runtime-pilot/v1", "context": context,
            "status": "synthetic-pilot-passed" if good else "blocked", "probes": probes,
            "cleanup_verified": cleanup_verified, "image": IMAGE,
            "fixture_sha256": hashlib.sha256(FIXTURE.encode()).hexdigest(),
            "provider_calls": 0, "runtime_qualified": False, "production_authorized": False,
            "evidence_kind": "synthetic-runtime-pilot-not-general-worker-qualification",
            "remaining_unobserved": ["credential-lease-revocation", "general-hostile-candidate-admission",
                                      "independent-workflow-identity-attestation", "cpu-saturation-enforcement"]}


class Docker:
    """No shell, inherited secrets, arbitrary host/daemon selection or login."""
    def __init__(self, scratch):
        self.environment = {"PATH": "/usr/bin:/bin", "HOME": str(scratch), "DOCKER_CONFIG": str(scratch / "docker-config")}
        (scratch / "docker-config").mkdir(mode=0o700)

    def call(self, args, timeout=12):
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run([DOCKER, *args], env=self.environment, stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                raise
            output.seek(0)
            data = output.read(131073)
        require(result.returncode == 0 and len(data) <= 131072, "bounded Docker command failed")
        return data.decode("utf-8").strip()

    def inspect(self, name):
        data = json.loads(self.call(["inspect", name]))
        require(isinstance(data, list) and len(data) == 1, "invalid Docker inspection")
        return data[0]

    def cleanup(self, identity):
        # Exactly this run/attempt only; do not enumerate or remove unrelated work.
        label = "label=c04-pilot=" + identity
        names = self.call(["ps", "-a", "--filter", label, "--format", "{{.Names}}"]).splitlines()
        allowed = {"c04-pilot-" + identity + "-" + probe for probe in PROBES}
        require(set(names) <= allowed, "unexpected container names; manual cleanup required")
        for name in names:
            self.call(["rm", "--force", name])
        require(not self.call(["ps", "-aq", "--filter", label]), "pilot teardown not proved")
        return True


def run_probe(docker, identity, probe, fixture):
    command = create_command(identity, probe, fixture)
    name = command[2]
    docker.call(command)
    validate_inspection(docker.inspect(name), identity, fixture)
    docker.call(["start", name])
    timed_out = False
    try:
        exit_code = int(docker.call(["wait", name], timeout=3 if probe == "timeout" else 15))
    except subprocess.TimeoutExpired:
        timed_out = True
        docker.call(["kill", name])
        exit_code = int(docker.call(["wait", name]))
    data = docker.inspect(name)
    state = data.get("State", {})
    require(state.get("Running") is False and state.get("ExitCode") == exit_code, "supervisor exit readback differs")
    row = {"probe": probe, "passed": False, "supervisor_exit_code": exit_code,
           "supervisor_timeout": timed_out, "supervisor_oom_killed": state.get("OOMKilled") is True}
    if probe == "oom":
        row["passed"] = exit_code == 137 and state.get("OOMKilled") is True and not timed_out
    elif probe == "timeout":
        row["passed"] = timed_out and exit_code == 137 and state.get("OOMKilled") is False
    elif not timed_out and exit_code == 0:
        report = json.loads(docker.call(["logs", name]))
        checks = report.get("checks", {})
        expected = ({"nonroot", "no_control_socket", "no_host_sentinel", "no_credentials", "no_caps",
                     "no_new_privileges", "fixture_readonly", "bounded_scratch_writable", "external_network_denied",
                     "cpu_cgroup_bound", "memory_cgroup_bound", "pids_cgroup_bound"} if probe == "baseline"
                    else {"pids_enforced"})
        row["passed"] = (report.get("probe") == probe and set(checks) == expected
                         and all(v is True for v in checks.values()) and state.get("OOMKilled") is False)
        row["checks"] = {key: checks.get(key) is True for key in sorted(expected)}
    return row


def execute(docker, context, scratch):
    identity = str(context["run_id"]) + "-" + str(context["run_attempt"])
    probes, clean = [], False
    try:
        docker.call(["pull", "--platform=linux/amd64", IMAGE], timeout=60)
        image = json.loads(docker.call(["image", "inspect", IMAGE]))[0]
        require(image.get("Os") == "linux" and image.get("Architecture") == "amd64"
                and any(d.endswith(IMAGE.split("@", 1)[1]) for d in image.get("RepoDigests", [])), "image identity not observed")
        context = {**context, "docker_server_version": docker.call(["version", "--format", "{{.Server.Version}}"]),
                   "kernel": platform.release(), "python": platform.python_version(), "local_image_id": image.get("Id")}
        fixture = scratch / "probe.py"
        (scratch / "host-only-sentinel").write_text("synthetic-host-marker-not-mounted")
        fixture.write_text(FIXTURE)
        fixture.chmod(0o444)
        scratch.chmod(0o755)
        for probe in PROBES:
            row = run_probe(docker, identity, probe, fixture)
            probes.append(row)
            if not row["passed"]:
                break
    except (PilotError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        # Never echo Docker output, ambient environment or source exception bodies.
        pass
    finally:
        try:
            clean = docker.cleanup(identity)
        except (PilotError, OSError, ValueError, subprocess.TimeoutExpired):
            clean = False
    return make_receipt(context, probes, clean)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--execute-hosted-pilot", action="store_true")
    modes.add_argument("--cleanup-hosted-pilot", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        context = hosted_context(os.environ, event)
        require(Path(DOCKER).is_file(), "runner Docker unavailable; do not install/fallback")
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(PilotError("pilot interrupted")))
        with tempfile.TemporaryDirectory(prefix="c04-pilot-") as directory:
            scratch = Path(directory)
            docker = Docker(scratch)
            if args.cleanup_hosted_pilot:
                return 0 if docker.cleanup(str(context["run_id"]) + "-" + str(context["run_attempt"])) else 1
            require(args.receipt is not None, "missing sanitized receipt output")
            result = execute(docker, context, scratch)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + chr(10))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "synthetic-pilot-passed" else 1
    except (PilotError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        print("C04 pilot blocked: hosted context, runtime or cleanup not proved; no fallback.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
