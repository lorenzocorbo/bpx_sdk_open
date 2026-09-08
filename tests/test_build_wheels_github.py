"""Offline checks for remote wheel builds and downloads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location(
    'wheels', Path(__file__).resolve().parents[1] / 'scripts/build_wheels_github.py')
wheels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wheels)


class WheelBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'wheel output'
        self.output.mkdir()
        (self.output / 'keep.txt').write_text('keep')
        self.calls = []
        self.platforms = {
            'bpx-sdk-open-wheels-ubuntu-22.04': ['manylinux_2_28_x86_64', 'manylinux_2_28_aarch64'],
            'bpx-sdk-open-wheels-windows-2022': ['win_amd64'],
            'bpx-sdk-open-wheels-macos-14': ['macosx_11_0_arm64'],
        }
        self.failed = False
        self.corrupt = False
        self.version_mismatch = False
        self.download_failure = False

    def command(self, args, timeout=60):
        if args[:3] == ['git', 'remote', 'get-url']:
            return 'git@github.com:mirrormerobotics/bpx_sdk_open.git'
        self.calls.append(args)
        if args[1] == 'api':
            if any('/jobs?' in arg for arg in args):
                return json.dumps({'jobs': [], 'total_count': 0})
            if 'POST' in args:
                self.assertIn('repos/mirrormerobotics/bpx_sdk_open/actions/workflows/build-wheels.yml/dispatches', args)
                self.assertIn('ref=master', args)
                return json.dumps({'workflow_run_id': 123})
            return json.dumps({'path': '.github/workflows/build-wheels.yml', 'status': 'completed',
                               'conclusion': 'failure' if self.failed else 'success', 'head_sha': 'abcdef'})
        self.assertEqual(args[:4], ['gh', 'run', 'download', '123'])
        artifact = args[args.index('--name') + 1]
        if self.download_failure and 'macos' in artifact:
            raise RuntimeError('下载失败')
        directory = Path(args[args.index('--dir') + 1])
        directory.mkdir(parents=True)
        for platform in self.platforms[artifact]:
            version = '1.0.9' if self.version_mismatch and 'macos' in artifact else '1.0.8'
            path = directory / f'bpx_sdk_open-{version}-cp311-cp311-{platform}.whl'
            if self.corrupt and 'macos' in artifact:
                path.write_bytes(b'broken zip')
                continue
            with zipfile.ZipFile(path, 'w') as wheel:
                for name in ['WHEEL', 'METADATA', 'RECORD']:
                    wheel.writestr(f'bpx_sdk_open-{version}.dist-info/{name}', 'metadata')
        return ''

    def run_script(self, *extra):
        def usage(repo):
            self.assertEqual(len(list(self.output.glob('*.whl'))), 4)
            self.assertEqual(repo, 'mirrormerobotics/bpx_sdk_open')
            return False  # Billing errors must not invalidate a completed download.
        with mock.patch.object(wheels, 'command', side_effect=self.command), \
                mock.patch.object(wheels.shutil, 'which', return_value='gh'), \
                mock.patch.object(wheels, 'show_usage', side_effect=usage) as query:
            result = wheels.main(['--out-dir', str(self.output), *extra])
            if '--show-usage' in extra:
                query.assert_called_once()
            else:
                query.assert_not_called()
            return result

    def test_dispatch_and_download_preserves_wheel_archives(self):
        self.assertEqual(self.run_script('--ref', 'master'), 0)
        self.assertEqual((self.output / 'keep.txt').read_text(), 'keep')
        self.assertEqual(len(list(self.output.iterdir())), 5)
        for path in self.output.glob('*.whl'):
            self.assertTrue(zipfile.is_zipfile(path))

    def test_opt_in_usage_after_download(self):
        self.assertEqual(self.run_script('--ref', 'master', '--show-usage'), 0)

    def test_resume_does_not_dispatch(self):
        self.assertEqual(self.run_script('--run-id', '123'), 0)
        self.assertFalse(any('POST' in args for args in self.calls))

    def test_build_failure_leaves_output_unchanged(self):
        self.failed = True
        with self.assertRaisesRegex(RuntimeError, '构建未成功'):
            self.run_script('--ref', 'master')
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(list(self.output.iterdir()), [self.output / 'keep.txt'])

    def test_download_failure_leaves_output_unchanged(self):
        self.download_failure = True
        with self.assertRaisesRegex(RuntimeError, '下载失败'):
            self.run_script('--run-id', '123')
        self.assertEqual(list(self.output.iterdir()), [self.output / 'keep.txt'])

    def test_corrupt_wheel_rejected(self):
        self.corrupt = True
        with self.assertRaisesRegex(RuntimeError, 'wheel 损坏'):
            self.run_script('--run-id', '123')
        self.assertEqual(list(self.output.iterdir()), [self.output / 'keep.txt'])

    def test_missing_linux_architecture_rejected(self):
        self.platforms['bpx-sdk-open-wheels-ubuntu-22.04'].pop()
        with self.assertRaisesRegex(RuntimeError, '缺少目标平台'):
            self.run_script('--run-id', '123')
        self.assertEqual(list(self.output.iterdir()), [self.output / 'keep.txt'])

    def test_mismatched_versions_rejected(self):
        self.version_mismatch = True
        with self.assertRaisesRegex(RuntimeError, '包版本不一致'):
            self.run_script('--run-id', '123')
        self.assertEqual(list(self.output.iterdir()), [self.output / 'keep.txt'])

    def test_usage_only(self):
        with mock.patch.object(wheels.shutil, 'which', return_value='gh'), \
                mock.patch.object(wheels, 'show_usage', return_value=True) as usage, \
                mock.patch.object(wheels, 'dispatch') as dispatch:
            self.assertEqual(wheels.main(['--usage-only', '--repo', 'mirrormerobotics/bpx_sdk_open']), 0)
        usage.assert_called_once_with('mirrormerobotics/bpx_sdk_open')
        dispatch.assert_not_called()


class ProgressTest(unittest.TestCase):
    def job(self, name, status, conclusion=None, steps=None):
        return {'name': name, 'status': status, 'conclusion': conclusion,
                'started_at': '2026-09-08T00:00:00Z',
                'completed_at': '2026-09-08T00:02:00Z' if status == 'completed' else None,
                'steps': steps or []}

    def test_platform_progress_and_current_step(self):
        jobs = [self.job('Build windows-2022 wheels', 'completed', 'success'),
                self.job('Build ubuntu-22.04 wheels', 'in_progress', steps=[
                    {'name': 'Set up Python', 'status': 'completed'},
                    {'name': 'Build wheels', 'status': 'in_progress'}]),
                self.job('Build macos-14 wheels', 'queued')]
        result = wheels.format_progress(jobs, 123)
        self.assertIn('50%', result)
        self.assertIn('已结束任务 1/3，成功 1', result)
        self.assertIn('当前：编译和测试 wheels', result)
        self.assertIn('Windows AMD64', result)
        self.assertIn('已等待 2分03秒', result)

    def test_unregistered_platforms_do_not_claim_full_progress(self):
        result = wheels.format_progress([self.job('linux', 'completed', 'success')], 1)
        self.assertIn('33%', result)
        self.assertIn('另有 2 个平台任务', result)

    def test_finished_failure_is_not_reported_as_success(self):
        jobs = [self.job('linux', 'completed', 'failure', [
                    {'name': 'Build wheels', 'status': 'completed', 'conclusion': 'failure'}]),
                self.job('windows', 'completed', 'success'), self.job('macos', 'completed', 'success')]
        result = wheels.format_progress(jobs, 100)
        self.assertIn('100%', result)
        self.assertIn('成功 2', result)
        self.assertIn('异常步骤：编译和测试 wheels', result)

    def test_missing_steps_does_not_divide_by_zero(self):
        self.assertIn('0%', wheels.format_progress([self.job('linux', 'queued')], 0))

    def test_current_attempt_and_pagination(self):
        with mock.patch.object(wheels, 'api', side_effect=[
            {'jobs': [{'id': 1}], 'total_count': 2},
            {'jobs': [{'id': 2}], 'total_count': 2},
        ]) as api:
            self.assertEqual(len(wheels.fetch_jobs('owner/repo', 123, 2)), 2)
        self.assertIn('/attempts/2/jobs?per_page=100&page=2', api.call_args.args[0])

    def test_progress_failure_does_not_stop_waiting(self):
        run = {'path': '.github/workflows/build-wheels.yml', 'status': 'completed',
               'conclusion': 'success', 'head_sha': 'abcdef'}
        with mock.patch.object(wheels, 'api', return_value=run), \
                mock.patch.object(wheels, 'fetch_jobs', side_effect=RuntimeError('HTTP 503')):
            wheels.wait_for_run('owner/repo', 123, 100, 10)


class RepositoryDetectionTest(unittest.TestCase):
    def test_common_remotes_and_forks(self):
        for remote in ['git@github.com:someone/bpx_sdk_open.git',
                       'https://github.com/someone/bpx_sdk_open.git',
                       'ssh://git@github.com/someone/bpx_sdk_open.git',
                       'https://github.com/someone/bpx_sdk_open/']:
            with mock.patch.object(wheels, 'command', return_value=remote):
                self.assertEqual(wheels.detect_repository(), 'someone/bpx_sdk_open')

    def test_non_github_remote_requires_explicit_repo(self):
        with mock.patch.object(wheels, 'command', return_value='git@example.com:owner/repo.git'):
            with self.assertRaisesRegex(RuntimeError, '--repo'):
                wheels.detect_repository()

    def test_missing_origin_requires_explicit_repo(self):
        with mock.patch.object(wheels, 'command', side_effect=RuntimeError('no origin')):
            with self.assertRaisesRegex(RuntimeError, '--repo'):
                wheels.detect_repository()

    def test_explicit_repo_overrides_origin(self):
        with mock.patch.object(wheels, 'detect_repository') as detect, \
                mock.patch.object(wheels.shutil, 'which', return_value='gh'), \
                mock.patch.object(wheels, 'show_usage', return_value=True) as usage:
            self.assertEqual(wheels.main(['--repo', 'someone/fork', '--usage-only']), 0)
        detect.assert_not_called()
        usage.assert_called_once_with('someone/fork')


if __name__ == '__main__':
    unittest.main()
