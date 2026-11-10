import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import contextlib
import io

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("c04_runtime_pilot", ROOT / "scripts/github/c04_runtime_pilot.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def environment():
    return {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "GITHUB_REPOSITORY": "fr-meyer/agent-toolkit",
            "GITHUB_REF": "refs/heads/feat/c04-provider-free-pilot-20261110", "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1"}


def event():
    return {"created": True, "deleted": False, "ref": environment()["GITHUB_REF"], "after": "a" * 40,
            "repository": {"full_name": "fr-meyer/agent-toolkit", "private": False}}


def inspection():
    return {"Config": {"Image": pilot.IMAGE, "User": "65534:65534", "Env": ["PATH=/usr/local/bin:/usr/bin:/bin"],
                       "Labels": {"c04-pilot": "1234-1"}},
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                           "CapDrop": ["ALL"], "CapAdd": None, "SecurityOpt": ["no-new-privileges"],
                           "NanoCpus": 1000000000, "Memory": 134217728, "MemorySwap": 134217728,
                           "PidsLimit": 32, "IpcMode": "none", "PidMode": "", "Binds": None,
                           "Tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=16m"}, "Devices": [],
                           "DeviceRequests": None, "VolumesFrom": None, "PortBindings": {}},
            "Mounts": [{"Type": "bind", "Source": "/tmp/fixture/probe.py", "Destination": "/probe.py", "RW": False}]}


class FakeDocker:
    def __init__(self, fixture, fail=None):
        self.fixture, self.fail = fixture, fail
        self.calls, self.cleaned, self.probe = [], False, None

    def call(self, command, timeout=12):
        self.calls.append(command)
        if self.fail == 'pull' and command[0] == 'pull':
            raise pilot.PilotError('synthetic denial')
        if command[:2] == ['image', 'inspect']:
            return json.dumps([{'Os':'linux','Architecture':'amd64','RepoDigests':[pilot.IMAGE],'Id':'sha256:fixture'}])
        if command[0] == 'version':
            return 'fixture-version'
        if command[0] == 'create':
            self.probe = command[-2]
        if command[0] == 'wait':
            if self.probe == 'timeout' and timeout == 3:
                raise subprocess.TimeoutExpired(command, timeout)
            return '137' if self.probe in ('oom','timeout') else '0'
        if command[0] == 'logs':
            names = ({'nonroot','no_control_socket','no_host_sentinel','no_credentials','no_caps',
                      'no_new_privileges','fixture_readonly','bounded_scratch_writable','external_network_denied',
                      'cpu_cgroup_bound','memory_cgroup_bound','pids_cgroup_bound'}
                     if self.probe == 'baseline' else {'pids_enforced'})
            return json.dumps({'probe':self.probe,'checks':{k:True for k in names}})
        return ''

    def inspect(self, name):
        result=inspection()
        result['Mounts'][0]['Source']=str(self.fixture)
        result['State']={'Running':False,'ExitCode':137 if self.probe in ('oom','timeout') else 0,
                         'OOMKilled':self.probe=='oom' and self.fail!='oom-attribution'}
        if self.fail == 'unsafe-config':
            result['HostConfig']['Privileged']=True
        return result

    def cleanup(self, identity):
        self.cleaned=True
        if self.fail == 'cleanup':
            raise pilot.PilotError('synthetic cleanup failure')
        return True


class RuntimePilotTests(unittest.TestCase):
    def test_valid_context_is_bound_to_public_new_branch(self):
        c = pilot.hosted_context(environment(), event())
        self.assertEqual(c["run_id"], 1234)
        self.assertEqual(c["run_attempt"], 1)
        self.assertEqual(c["head_sha"], "a" * 40)

    def test_local_target_fork_private_and_other_branches_fail_closed(self):
        for delta in ({"GITHUB_ACTIONS": "false"}, {"GITHUB_EVENT_NAME": "pull_request_target"},
                      {"RUNNER_ENVIRONMENT": "self-hosted"}, {"RUNNER_OS": "Windows"},
                      {"RUNNER_ARCH": "ARM64"}, {"GITHUB_REPOSITORY": "attacker/fork"},
                      {"GITHUB_REF": "refs/heads/main"}, {"GITHUB_WORKFLOW_SHA": "b" * 40},
                      {"GITHUB_SHA": "dev"}, {"GITHUB_RUN_ID": "1234; touch bad"}):
            with self.subTest(delta=delta), self.assertRaises(pilot.PilotError):
                pilot.hosted_context({**environment(), **delta}, event())
        for delta in ({"created": False}, {"deleted": True}, {"after": "b" * 40},
                      {"repository": {"full_name": "attacker/fork", "private": False}},
                      {"repository": {"full_name": "fr-meyer/agent-toolkit", "private": True}}):
            with self.subTest(delta=delta), self.assertRaises(pilot.PilotError):
                pilot.hosted_context(environment(), {**event(), **delta})

    def test_attempt_limit_is_enforced_before_docker(self):
        for attempt in ("0", "4", "true", "1.0", "-1"):
            with self.subTest(attempt=attempt), self.assertRaises(pilot.PilotError):
                pilot.hosted_context({**environment(), "GITHUB_RUN_ATTEMPT": attempt}, event())
        self.assertEqual(pilot.hosted_context({**environment(), "GITHUB_RUN_ATTEMPT": "3"}, event())["run_attempt"], 3)

    def test_command_uses_immutable_image_no_network_or_credentials(self):
        command = pilot.create_command("1234-1", "baseline", Path("/tmp/fixture/probe.py"))
        self.assertEqual(command[:2], ["create", "--name"])
        for arg in ("--read-only", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--user=65534:65534", "--memory=128m", "--memory-swap=128m", "--pids-limit=32", "--cpus=1"):
            self.assertIn(arg, command)
        self.assertIn(pilot.IMAGE, command)
        self.assertRegex(pilot.IMAGE, r"^docker.io/library/python@sha256:[0-9a-f]{64}$")
        self.assertEqual(command.count("--mount"), 1)
        self.assertNotIn("--privileged", command)
        self.assertNotIn("--env", command)
        self.assertNotIn("--volume", command)
        self.assertNotIn("docker.sock", " ".join(command))

    def test_arbitrary_probe_path_or_context_is_never_accepted(self):
        for args in (("1234-1", "arbitrary", Path("/tmp/fixture/probe.py")),
                     ("../host", "baseline", Path("/tmp/fixture/probe.py")),
                     ("1234-1", "baseline", Path("/tmp/path,with,commas/probe.py"))):
            with self.subTest(args=args), self.assertRaises(pilot.PilotError):
                pilot.create_command(*args)

    def test_supervisor_inspects_real_config_not_just_fixture_assertions(self):
        pilot.validate_inspection(inspection(), "1234-1", Path("/tmp/fixture/probe.py"))
        mutations = [("NetworkMode", "host"), ("Privileged", True), ("ReadonlyRootfs", False),
                     ("PidsLimit", 0), ("Memory", 0), ("MemorySwap", -1), ("NanoCpus", 0),
                     ("CapAdd", ["SYS_ADMIN"]), ("SecurityOpt", []), ("PidMode", "host"),
                     ("Binds", ["/:/host"]), ("Devices", [{"PathOnHost": "/dev/sda"}]),
                     ("PortBindings", {"80/tcp": []}), ("VolumesFrom", ["host"]),
                     ("Tmpfs", {}), ("IpcMode", "host")]
        for key, value in mutations:
            bad = inspection()
            bad["HostConfig"][key] = value
            with self.subTest(key=key), self.assertRaises(pilot.PilotError):
                pilot.validate_inspection(bad, "1234-1", Path("/tmp/fixture/probe.py"))

    def test_extra_mounts_image_or_env_cannot_cross_boundary(self):
        for mutate in (lambda d: d["Mounts"].append({"Type": "bind", "Destination": "/var/run/docker.sock"}),
                       lambda d: d["Mounts"][0].update(RW=True),
                       lambda d: d["Mounts"][0].update(Source="/etc"),
                       lambda d: d["Config"].update(User="root"),
                       lambda d: d["Config"].update(Image="python:latest"),
                       lambda d: d["Config"].update(Env=["GITHUB_TOKEN=synthetic"]),
                       lambda d: d["Config"]["Labels"].update({"c04-pilot": "other-run"})):
            bad = inspection()
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(pilot.PilotError):
                pilot.validate_inspection(bad, "1234-1", Path("/tmp/fixture/probe.py"))

    def test_successful_synthetic_receipt_never_qualifies_real_workers(self):
        c = pilot.hosted_context(environment(), event())
        r = pilot.make_receipt(c, [{"probe": p, "passed": True} for p in pilot.PROBES], True)
        self.assertEqual(r["status"], "synthetic-pilot-passed")
        self.assertFalse(r["runtime_qualified"])
        self.assertFalse(r["production_authorized"])
        self.assertEqual(r["provider_calls"], 0)
        self.assertIn("credential-lease-revocation", r["remaining_unobserved"])

    def test_missing_failed_or_duplicate_probe_and_cleanup_never_pass(self):
        c = pilot.hosted_context(environment(), event())
        good = [{"probe": p, "passed": True} for p in pilot.PROBES]
        for rows, clean in ((good[:-1], True), (good + good[:1], True),
                            ([{**x, "passed": False} for x in good], True), (good, False)):
            with self.subTest(rows=rows, clean=clean):
                self.assertEqual(pilot.make_receipt(c, rows, clean)["status"], "blocked")

    def test_fixture_is_synthetic_and_syntax_valid(self):
        compile(pilot.FIXTURE, "synthetic_probe", "exec")
        self.assertNotIn("requests", pilot.FIXTURE)
        self.assertNotIn("https://", pilot.FIXTURE)
        self.assertIn("range(40)", pilot.FIXTURE)
        self.assertIn("range(20)", pilot.FIXTURE)

    def test_entire_supervisor_success_path_is_mocked_not_hosted_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            docker=FakeDocker(root/'probe.py')
            result=pilot.execute(docker,pilot.hosted_context(environment(),event()),root)
            self.assertEqual(result['status'],'synthetic-pilot-passed')
            self.assertFalse(result['runtime_qualified'])
            self.assertTrue(docker.cleaned)
            self.assertTrue((root/'host-only-sentinel').is_file())
            self.assertEqual(len([c for c in docker.calls if c[0]=='create']),4)
            self.assertEqual(len([c for c in docker.calls if c[0]=='kill']),1)

    def test_pull_inspect_oom_attribution_and_cleanup_failures_stop_closed(self):
        for failure in ('pull','unsafe-config','oom-attribution','cleanup'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                docker=FakeDocker(Path(directory)/'probe.py',fail=failure)
                result=pilot.execute(docker,pilot.hosted_context(environment(),event()),Path(directory))
                self.assertEqual(result['status'],'blocked')
                self.assertTrue(docker.cleaned)
                if failure=='pull':
                    self.assertFalse(any(c[0]=='create' for c in docker.calls))

    def test_docker_client_drops_ambient_credentials_and_daemon_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            docker=pilot.Docker(Path(directory))
            def run(command,**kwargs):
                self.assertEqual(command[0],'/usr/bin/docker')
                self.assertEqual(set(kwargs['env']),{'PATH','HOME','DOCKER_CONFIG'})
                self.assertNotIn('shell',kwargs)
                self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)
                kwargs['stdout'].write(b'fixture')
                return subprocess.CompletedProcess(command,0)
            with patch.object(pilot.subprocess,'run',side_effect=run):
                self.assertEqual(docker.call(['version']),'fixture')

    def test_cleanup_can_only_remove_exact_run_probe_names(self):
        with tempfile.TemporaryDirectory() as directory:
            docker=pilot.Docker(Path(directory))
            with patch.object(docker,'call',side_effect=['unrelated-host-container']) as call:
                with self.assertRaises(pilot.PilotError):
                    docker.cleanup('1234-1')
                self.assertEqual(call.call_count,1)
            with patch.object(docker,'call',side_effect=['c04-pilot-1234-1-baseline','','']) as call:
                self.assertTrue(docker.cleanup('1234-1'))
                self.assertEqual(call.call_args_list[1].args[0],['rm','--force','c04-pilot-1234-1-baseline'])

    def test_bad_local_cli_context_cannot_touch_docker_or_emit_success_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            metadata=root/'event.json'
            metadata.write_text(json.dumps(event()))
            output=root/'receipt.json'
            with patch('sys.argv',['pilot','--execute-hosted-pilot','--receipt',str(output)]), \
                 patch.dict(pilot.os.environ,{**environment(),'GITHUB_ACTIONS':'false','GITHUB_EVENT_PATH':str(metadata)},clear=True), \
                 patch.object(pilot,'Docker') as docker, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pilot.main(),1)
                docker.assert_not_called()
            self.assertFalse(output.exists())

    def test_malformed_or_oversized_docker_output_fails_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            docker=pilot.Docker(Path(directory))
            def run(command,**kwargs):
                kwargs['stdout'].write(b'x'*131073)
                return subprocess.CompletedProcess(command,0)
            with patch.object(pilot.subprocess,'run',side_effect=run):
                with self.assertRaises(pilot.PilotError) as error:
                    docker.call(['version'])
                self.assertNotIn('xxx',str(error.exception))

    def test_workflow_is_only_exact_branch_create_push(self):
        text = (ROOT / "templates/starter-workflows/c04-runtime-pilot.yml").read_text()
        self.assertEqual(text, (ROOT / ".github/workflows/c04-runtime-pilot.yml").read_text())
        self.assertIn("      - feat/c04-provider-free-pilot-20261110", text)
        self.assertIn("github.event.created == true", text)
        self.assertIn("fromJSON(github.run_attempt) <= 3", text)
        self.assertIn("timeout-minutes: 5", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("if: " + chr(36) + "{{ always() }}", text)
        for value in ("workflow_dispatch:", "pull_request:", "schedule:", "secrets:", "secrets.",
                      "upload-artifact", "cache@", "contents: write", "cancel-in-progress: true"):
            self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
