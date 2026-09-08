"""Regression tests for interrupted GitHub status polling."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('wheels', Path(__file__).resolve().parents[1] / 'scripts/build_wheels_github.py')
wheels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wheels)
RESET = RuntimeError('命令执行失败（退出码 1）：read tcp: read: connection reset by peer')
RUN = {'path': '.github/workflows/build-wheels.yml', 'status': 'completed', 'conclusion': 'success', 'head_sha': 'test'}
JOBS = [{'name': 'Build ubuntu-22.04 wheels', 'status': 'completed', 'conclusion': 'success'}]


class PollingTest(unittest.TestCase):
    def test_job_then_run_connection_reset_recovers_same_run(self):
        stream = io.StringIO()
        with mock.patch.object(wheels.sys, 'stdout', stream), \
                mock.patch.object(wheels, 'api', side_effect=[dict(RUN, status='in_progress', conclusion=None), RESET, RUN]) as api, \
                mock.patch.object(wheels, 'fetch_jobs', side_effect=[RESET, JOBS]), \
                mock.patch.object(wheels.time, 'sleep'):
            result = wheels.wait_for_run('owner/repo', 123, 60, 1)
        self.assertEqual(len(result), 3)
        self.assertEqual(api.call_count, 3)
        for call in api.call_args_list:
            self.assertEqual(call.args[0], 'repos/owner/repo/actions/runs/123')
        self.assertIn('暂时无法获取构建状态', stream.getvalue())

    def test_completed_run_retries_job_lookup(self):
        with mock.patch.object(wheels.sys, 'stdout', io.StringIO()), \
                mock.patch.object(wheels, 'api', return_value=RUN) as api, \
                mock.patch.object(wheels, 'fetch_jobs', side_effect=[RESET, RESET, JOBS]), \
                mock.patch.object(wheels.time, 'sleep'):
            result = wheels.wait_for_run('owner/repo', 123, 60, 1)
        self.assertEqual(len(result), 3)
        self.assertEqual(api.call_count, 3)

    def test_network_failure_respects_deadline(self):
        with mock.patch.object(wheels.sys, 'stdout', io.StringIO()), \
                mock.patch.object(wheels, 'api', side_effect=RESET), \
                mock.patch.object(wheels.time, 'monotonic', side_effect=[0, 1, 2, 3]), \
                mock.patch.object(wheels.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, '--run-id 123'):
                wheels.wait_for_run('owner/repo', 123, 1, 1)

    def test_permission_error_is_not_retried(self):
        with mock.patch.object(wheels.sys, 'stdout', io.StringIO()), \
                mock.patch.object(wheels, 'api', side_effect=RuntimeError('HTTP 403: forbidden')), \
                mock.patch.object(wheels.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, '403'):
                wheels.wait_for_run('owner/repo', 123, 60, 1)
        sleep.assert_not_called()
