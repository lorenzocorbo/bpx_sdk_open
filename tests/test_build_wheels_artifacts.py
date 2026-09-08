"""Offline coverage for native ARM jobs and legacy combined Linux artifacts."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location(
    'wheels', Path(__file__).resolve().parents[1] / 'scripts/build_wheels_github.py')
wheels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wheels)


class ArtifactTest(unittest.TestCase):
    def make_artifacts(self, directory, artifacts):
        for name, archs in artifacts.items():
            root = directory / name
            root.mkdir()
            for arch in archs:
                platform = ('manylinux_2_28_' + arch if 'ubuntu' in name else
                            'macosx_11_0_' + arch if 'macos' in name else arch)
                with zipfile.ZipFile(root / ('bpx_sdk_open-1.0.9-cp38-cp38-' + platform + '.whl'), 'w') as wheel:
                    for metadata in ('WHEEL', 'METADATA', 'RECORD'):
                        wheel.writestr('bpx_sdk_open-1.0.9.dist-info/' + metadata, 'test metadata')

    def test_four_native_artifacts_and_missing_arm(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_artifacts(root, wheels.ARTIFACTS)
            self.assertEqual(len(wheels.collect_wheels(root)), 4)
            arm = root / 'bpx-sdk-open-wheels-ubuntu-22.04-arm'
            for path in arm.iterdir():
                path.unlink()
            arm.rmdir()
            with self.assertRaisesRegex(RuntimeError, '缺少 wheel 产物.*ubuntu-22.04-arm'):
                wheels.collect_wheels(root)

    def test_arm_job_rejects_x86_wheel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wrong = dict(wheels.ARTIFACTS)
            wrong['bpx-sdk-open-wheels-ubuntu-22.04-arm'] = ('x86_64',)
            self.make_artifacts(root, wrong)
            with self.assertRaisesRegex(RuntimeError, '缺少目标平台.*aarch64'):
                wheels.collect_wheels(root)

    def test_legacy_run_download_and_progress(self):
        jobs = [{'name': 'Build ' + os + ' wheels', 'status': 'completed', 'conclusion': 'success'}
                for os in ('ubuntu-22.04', 'windows-2022', 'macos-14')]
        artifacts = wheels.artifacts_for_jobs(jobs)
        self.assertEqual(len(artifacts), 3)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_artifacts(root, artifacts)
            self.assertEqual(len(wheels.collect_wheels(root, artifacts)), 4)
        with mock.patch.object(wheels.sys, 'stdout', io.StringIO()):
            output = wheels.format_progress(jobs, 1)
        self.assertIn('100%；已结束任务 3/3', output)
        self.assertIn('Linux x86_64/aarch64', output)

    def test_native_progress_and_run_artifacts(self):
        jobs = [{'name': 'Build ' + name + ' wheels', 'status': 'completed', 'conclusion': 'success'}
                for name in ('ubuntu-22.04 x86_64', 'ubuntu-22.04-arm aarch64',
                             'windows-2022 AMD64', 'macos-14 arm64')]
        run = {'path': '.github/workflows/build-wheels.yml', 'status': 'completed',
               'conclusion': 'success', 'head_sha': 'test'}
        with mock.patch.object(wheels.sys, 'stdout', io.StringIO()), \
                mock.patch.object(wheels, 'api', return_value=run), \
                mock.patch.object(wheels, 'fetch_jobs', return_value=jobs):
            artifacts = wheels.wait_for_run('owner/repo', 1, 30, 1)
            output = wheels.format_progress(jobs, 1)
        self.assertEqual(artifacts, wheels.ARTIFACTS)
        self.assertIn('100%；已结束任务 4/4', output)
        self.assertIn('Linux x86_64：', output)
        self.assertIn('Linux aarch64：', output)
        self.assertNotIn('Linux x86_64/aarch64', output)
