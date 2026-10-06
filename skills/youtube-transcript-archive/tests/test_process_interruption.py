"""Offline callback regressions: never start yt-dlp or a provider request."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import traceback
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/archive_youtube_transcript.py'
spec = importlib.util.spec_from_file_location('interruption_archive', SCRIPT)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
CHOICES = [('en', 'automatic', []), ('fr', 'automatic', []), ('de', 'automatic', [])]


class ProcessInterruptionTests(unittest.TestCase):
    def test_fresh_circuits_stop_after_first_caption_candidate(self):
        cases = (
            ('bot_check', "ERROR: Sign in to confirm you're not a bot"),
            ('bot_check', 'ERROR: CAPTCHA required after unusual traffic'),
            ('rate_limited', 'ERROR: HTTP Error 429: Too Many Requests'),
            ('auth_required', 'ERROR: Authentication required; login required'),
        )
        for failure_class, diagnostic in cases:
            with self.subTest(failure_class=failure_class, diagnostic=diagnostic):
                calls = []
                def download(lang, source):
                    calls.append(lang)
                    raise subprocess.CalledProcessError(1, ['synthetic'], stderr=diagnostic)
                with self.assertRaises(archive.YtDlpCircuitBlocked) as raised:
                    archive.select_caption_vtt(CHOICES, 'best', False, download)
                self.assertEqual(raised.exception.failure_class, failure_class)
                self.assertEqual(calls, ['en'])

    def test_fresh_circuit_after_ordinary_failure_stops_remaining_candidates(self):
        calls = []
        def download(lang, source):
            calls.append(lang)
            if lang == 'en':
                raise RuntimeError('synthetic unavailable caption track')
            raise RuntimeError('ERROR: too many requests')
        with self.assertRaises(archive.YtDlpCircuitBlocked) as raised:
            archive.select_caption_vtt(CHOICES, 'best', False, download)
        self.assertEqual(raised.exception.failure_class, 'rate_limited')
        self.assertEqual(calls, ['en', 'fr'])

    def test_process_boundary_propagates_circuits_through_every_helper(self):
        helpers = (
            (archive.list_subs, ('synthetic', 'https://example.invalid/')),
            (archive.yt_dlp_version, ('synthetic',)),
            (archive.load_json_from_yt_dlp, ('synthetic', 'https://example.invalid/')),
        )
        for failure_class, diagnostic in (
            ('bot_check', "ERROR: confirm you’re not a bot"),
            ('rate_limited', 'ERROR: HTTP Error 429'),
            ('auth_required', 'ERROR: login required'),
        ):
            for helper, args in helpers:
                with self.subTest(failure_class=failure_class, helper=helper.__name__):
                    error = subprocess.CalledProcessError(1, ['synthetic', '--password', 'synthetic-command-secret'], output=diagnostic, stderr='WARNING: No supported JavaScript runtime could be found')
                    with patch.object(archive.subprocess, 'run', side_effect=error) as spawn:
                        with self.assertRaises(archive.YtDlpCircuitBlocked) as raised:
                            helper(*args)
                    self.assertEqual(raised.exception.failure_class, failure_class)
                    self.assertEqual(spawn.call_count, 1)
                    self.assertNotIn('synthetic-command-secret', str(raised.exception))

    def test_shutdown_wins_over_every_fresh_circuit(self):
        for diagnostic in ('ERROR: CAPTCHA required', 'ERROR: HTTP Error 429', 'ERROR: login required'):
            with self.subTest(diagnostic=diagnostic):
                error = subprocess.CalledProcessError(1, ['synthetic'], output='ERROR: underlying process returned 0xC000026B', stderr=diagnostic)
                with patch.object(archive.subprocess, 'run', side_effect=error):
                    with self.assertRaises(archive.YtDlpProcessInterrupted) as raised:
                        archive.yt_dlp_version('synthetic')
                self.assertIn('0xC000026B', str(raised.exception))
                self.assertIn('underlying process returned', str(raised.exception))

    def test_wrapped_shutdown_stdout_and_bytes_survive_stderr_warning_and_bound(self):
        cases = (
            (3221226091, ''),
            (-1073741205, ''),
            (1, 'ERROR: window station is shutting down'),
            (1, 'ERROR: underlying process returned -1073741205'),
            (1, b'ERROR: underlying process returned 3221226091'),
            (1, 'ERROR: underlying process returned 0xC000026B'),
        )
        for code, output in cases:
            with self.subTest(code=code, output=output):
                error = subprocess.CalledProcessError(code, ['synthetic'], output=output, stderr='WARNING: ' + 'irrelevant ' * 8000)
                with patch.object(archive.subprocess, 'run', side_effect=error):
                    with self.assertRaises(archive.YtDlpProcessInterrupted) as raised:
                        archive.load_json_from_yt_dlp('synthetic', 'https://example.invalid/')
                summary = str(raised.exception)
                self.assertLessEqual(len(summary), 500)
                self.assertIn('0xC000026B', summary)
                if output:
                    expected = output.decode() if isinstance(output, bytes) else output
                    self.assertIn(expected, summary)

    def test_late_shutdown_and_circuit_diagnostics_survive_long_single_lines(self):
        for diagnostic, expected in (
            ('window station is shutting down', '0xC000026B'),
            ('HTTP Error 429', 'rate_limited'),
            ('authentication required', 'auth_required'),
            ('CAPTCHA required', 'bot_check'),
        ):
            with self.subTest(diagnostic=diagnostic):
                error = subprocess.CalledProcessError(1, ['synthetic'], stderr='ERROR: ' + 'irrelevant ' * 8000 + diagnostic)
                summary = archive.caption_error_summary(error)
                self.assertLessEqual(len(summary), 500)
                self.assertIn(expected, summary)
                self.assertIn(diagnostic, summary)

    def test_cookie_jwt_signed_query_and_existing_credentials_are_redacted(self):
        jwt = 'eyJmaXh0dXJl.c3ludGhldGlj.c2lnbmF0dXJl'
        secrets = ('synthetic-cookie-secret', 'synthetic-header-secret', 'synthetic-query-secret', 'synthetic-fragment-secret', 'synthetic-url-secret', 'synthetic-cli-secret', 'synthetic-json-secret', jwt)
        detail = (
            'Cookie: session=synthetic-cookie-secret\nSet-Cookie: session=synthetic-cookie-secret\n'
            'Authorization: Bearer synthetic-header-secret\n'
            'HTTPS://fixture:synthetic-url-secret@example.invalid/caption?sig=synthetic-query-secret#synthetic-fragment-secret\n'
            '--password synthetic-cli-secret\n{"token":"synthetic-json-secret"}\n' + jwt
        )
        sanitized = archive.sanitize_caption_error(detail)
        for secret in secrets:
            self.assertNotIn(secret, sanitized)
        self.assertIn('example.invalid/caption', sanitized)

    def test_long_sensitive_field_is_redacted_before_diagnostic_bound(self):
        error = subprocess.CalledProcessError(3221226091, ['synthetic'], stderr='Cookie: ' + 'synthetic-cookie-secret' * 4000)
        summary = archive.caption_error_summary(error)
        self.assertLessEqual(len(summary), 500)
        self.assertIn('0xC000026B', summary)
        self.assertNotIn('synthetic-cookie', summary)
        self.assertIn('[redacted sensitive header]', summary)

    def test_optional_subtitle_listing_failure_redacts_captured_credentials(self):
        jwt = 'eyJmaXh0dXJl.c3ludGhldGlj.c2lnbmF0dXJl'
        error = subprocess.CalledProcessError(1, ['synthetic'], output='https://example.invalid/caption?sig=synthetic-query-secret\n' + jwt, stderr='ordinary fixture failure\nCookie: session=synthetic-cookie-secret')
        with patch.object(archive.subprocess, 'run', side_effect=error):
            listing = archive.list_subs('synthetic', 'https://example.invalid/')
        self.assertIn('ordinary fixture failure', listing)
        for secret in ('synthetic-query-secret', 'synthetic-cookie-secret', jwt):
            self.assertNotIn(secret, listing)

    def test_fresh_circuit_traceback_is_sanitized_and_existing_artifacts_preserved(self):
        jwt = 'eyJmaXh0dXJl.c3ludGhldGlj.c2lnbmF0dXJl'
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / 'synthetic-existing-caption.vtt'
            artifact.write_text('synthetic archived caption', encoding='utf-8')
            calls = []
            def download(lang, source):
                calls.append(lang)
                archive.run(['synthetic', '--password', 'synthetic-command-secret'])
                self.fail('fresh circuit continued to artifact creation')
            error = subprocess.CalledProcessError(1, ['synthetic', '--password', 'synthetic-command-secret'], stderr='ERROR: HTTP Error 429\nCookie: session=synthetic-cookie-secret\n' + jwt)
            with patch.object(archive.subprocess, 'run', side_effect=error) as spawn:
                try:
                    archive.select_caption_vtt(CHOICES, 'best', False, download)
                except archive.YtDlpCircuitBlocked:
                    public = traceback.format_exc()
                else:
                    self.fail('fresh circuit did not stop')
            self.assertEqual(calls, ['en'])
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(artifact.read_text(encoding='utf-8'), 'synthetic archived caption')
            self.assertEqual(list(Path(directory).iterdir()), [artifact])
        for secret in ('synthetic-command-secret', 'synthetic-cookie-secret', jwt):
            self.assertNotIn(secret, public)

    def test_explicit_nonfatal_error_public_traceback_does_not_expose_process_command(self):
        def download(lang, source):
            raise subprocess.CalledProcessError(1, ['synthetic', '--password', 'synthetic-command-secret'], stderr='ERROR: caption track unavailable\nCookie: session=synthetic-cookie-secret')
        try:
            archive.select_caption_vtt(CHOICES, 'en', False, download)
        except RuntimeError:
            public = traceback.format_exc()
        else:
            self.fail('explicit caption failure did not stop')
        self.assertNotIn('synthetic-command-secret', public)
        self.assertNotIn('synthetic-cookie-secret', public)
        self.assertIn('caption track unavailable', public)

    def test_unsigned_and_signed_status_stop_after_first_attempt(self):
        for status in (3221226091, -1073741205):
            calls = []
            def download(lang, source):
                calls.append(lang)
                raise subprocess.CalledProcessError(status, ['synthetic'], stderr='ERROR: window station is shutting down')
            with self.assertRaisesRegex(RuntimeError, '0xC000026B'):
                archive.select_caption_vtt(CHOICES, 'best', False, download)
            self.assertEqual(calls, ['en'])

    def test_original_mixed_runtime_warning_and_fatal_second_attempt_stops(self):
        calls = []
        def download(lang, source):
            calls.append(lang)
            if len(calls) == 1:
                raise subprocess.CalledProcessError(1, ['synthetic'], stderr='WARNING: No supported JavaScript runtime could be found')
            raise subprocess.CalledProcessError(3221226091, ['synthetic'], stderr='')
        with self.assertRaisesRegex(RuntimeError, 'STATUS_DLL_INIT_FAILED_LOGOFF'):
            archive.select_caption_vtt(CHOICES, 'best', False, download)
        self.assertEqual(calls, ['en', 'fr'])

    def test_nonfatal_error_keeps_existing_fallback(self):
        calls = []
        def download(lang, source):
            calls.append(lang)
            if lang == 'en':
                raise subprocess.CalledProcessError(1, ['synthetic'], stderr='ERROR: selected caption unavailable')
            return Path('fixture.vtt')
        selected = archive.select_caption_vtt(CHOICES, 'best', False, download)
        self.assertEqual(selected[:3], ('fr', 'automatic', Path('fixture.vtt')))
        self.assertEqual(calls, ['en', 'fr'])

    def test_fatal_error_line_survives_warning_prefix_and_bound(self):
        error = subprocess.CalledProcessError(3221226091, ['synthetic'], stderr='WARNING: '+('irrelevant '*80)+'\nERROR: window station is shutting down')
        summary = archive.caption_error_summary(error)
        self.assertLessEqual(len(summary), 500)
        self.assertIn('0xC000026B', summary)
        self.assertIn('ERROR: window station is shutting down', summary)

    def test_credential_values_are_removed_from_summary_and_public_traceback(self):
        diagnostic = 'ERROR: API_KEY=fixture-key Authorization: Bearer fixture-header'
        def download(lang, source):
            raise subprocess.CalledProcessError(3221226091, ['synthetic', '--password', 'fixture-password'], stderr=diagnostic)
        try:
            archive.select_caption_vtt(CHOICES, 'best', False, download)
        except RuntimeError:
            public = traceback.format_exc()
        else:
            self.fail('fatal process did not stop')
        for secret in ('fixture-key', 'fixture-header', 'fixture-password'):
            self.assertNotIn(secret, public)
        self.assertIn('0xC000026B', public)

    def test_wrapped_status_and_hex_interruptions_stop_fallback(self):
        for detail in ('status 3221226091', 'status -1073741205', 'status 0xC000026B'):
            calls=[]
            def download(lang, source):
                calls.append(lang)
                raise RuntimeError(detail)
            with self.assertRaises(RuntimeError):
                archive.select_caption_vtt(CHOICES, 'best', False, download)
            self.assertEqual(calls, ['en'])

    def test_unrelated_dll_failure_keeps_fallback(self):
        self.assertFalse(archive.caption_process_interrupted(subprocess.CalledProcessError(0xC0000142, ['synthetic'])))

    def test_wrapper_exit_one_with_fatal_stderr_stops_fallback(self):
        calls=[]
        def download(lang, source):
            calls.append(lang)
            raise subprocess.CalledProcessError(1,['synthetic'],stderr='ERROR: underlying process returned 0xC000026B')
        with self.assertRaisesRegex(RuntimeError,'0xC000026B'):
            archive.select_caption_vtt(CHOICES,'best',False,download)
        self.assertEqual(calls,['en'])

    def test_json_and_escaped_credential_values_are_redacted(self):
        for detail in ['{"token":"fixture-json-secret"}', '{"password":"fixture-escaped-secret \\" more"}', '{"Authorization":"fixture-json-header"}']:
            safe=archive.sanitize_caption_error(detail)
            self.assertNotIn('fixture-',safe)

    def test_process_boundary_propagates_fatal_status_through_every_helper(self):
        for helper, args in [(archive.list_subs,('synthetic','https://example.invalid/')),(archive.yt_dlp_version,('synthetic',)),(archive.load_json_from_yt_dlp,('synthetic','https://example.invalid/'))]:
            error=subprocess.CalledProcessError(3221226091,['synthetic','--password','fixture-command-secret'],stderr='ERROR: window station is shutting down\n{"token":"fixture-json-secret"}')
            with patch.object(archive.subprocess,'run',side_effect=error) as spawn:
                try:
                    helper(*args)
                except archive.YtDlpProcessInterrupted:
                    public=traceback.format_exc()
                else:
                    self.fail('fatal helper process was swallowed')
            self.assertEqual(spawn.call_count,1)
            self.assertIn('0xC000026B',public)
            self.assertNotIn('fixture-command-secret',public);self.assertNotIn('fixture-json-secret',public)

    def test_nonfatal_helper_failures_keep_existing_optional_behavior(self):
        error=subprocess.CalledProcessError(1,['synthetic'],stderr='ordinary fixture failure')
        with patch.object(archive.subprocess,'run',side_effect=error):
            self.assertEqual(archive.yt_dlp_version('synthetic'),'unknown')
            self.assertEqual(archive.list_subs('synthetic','https://example.invalid/'),'ordinary fixture failure')

if __name__ == '__main__':
    unittest.main()
