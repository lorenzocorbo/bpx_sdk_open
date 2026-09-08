"""Offline checks for terminal colors in wheel build output."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "wheels", Path(__file__).resolve().parents[1] / "scripts/build_wheels_github.py")
wheels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wheels)


class HighlightTest(unittest.TestCase):
    def test_success_failure_and_cancelled_colors(self):
        terminal = mock.Mock()
        terminal.isatty.return_value = True
        with mock.patch.dict(wheels.os.environ, {"TERM": "xterm"}, clear=True):
            self.assertEqual(wheels.highlight("成功", "success", terminal), "\033[1;32m成功\033[0m")
            self.assertEqual(wheels.highlight("失败", "failure", terminal), "\033[1;31m失败\033[0m")
            self.assertEqual(wheels.highlight("已取消", "cancelled", terminal), "\033[1;33m已取消\033[0m")
            self.assertEqual(wheels.highlight("运行中", "in_progress", terminal), "\033[1;33m运行中\033[0m")

    def test_redirected_output_no_color_and_dumb_terminal(self):
        terminal = mock.Mock()
        terminal.isatty.return_value = True
        self.assertEqual(wheels.highlight("成功", "success", io.StringIO()), "成功")
        self.assertEqual(wheels.highlight("运行中", "in_progress", io.StringIO()), "运行中")
        for env in ({"NO_COLOR": "1"}, {"NO_COLOR": ""}, {"TERM": "dumb"}):
            with mock.patch.dict(wheels.os.environ, env, clear=True):
                self.assertEqual(wheels.highlight("失败", "failure", terminal), "失败")
                self.assertEqual(wheels.highlight("运行中", "in_progress", terminal), "运行中")

    def test_job_and_run_results_are_highlighted(self):
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        run = {"path": ".github/workflows/build-wheels.yml", "status": "completed",
               "conclusion": "success", "head_sha": "abc123"}
        jobs = [{"name": "Build linux SDK", "status": "completed", "conclusion": "success"},
                {"name": "windows-2022", "status": "completed", "conclusion": "failure"}]
        with mock.patch.dict(wheels.os.environ, {"TERM": "xterm"}, clear=True), \
                mock.patch("sys.stdout", terminal), \
                mock.patch.object(wheels, "api", side_effect=[dict(run, status="in_progress", conclusion=None), run]), \
                mock.patch.object(wheels.time, "sleep"), \
                mock.patch.object(wheels, "fetch_jobs", side_effect=[
                    [dict(jobs[0], status="in_progress", conclusion=None), jobs[1]], jobs]):
            wheels.wait_for_run("owner/repo", 456, 100, 10)
        output = terminal.getvalue()
        self.assertIn("构建状态：\033[1;33m运行中\033[0m", output)
        self.assertIn("Build linux SDK：\033[1;33m运行中\033[0m", output)
        self.assertIn("构建状态：已完成 / \033[1;32m成功\033[0m", output)
        self.assertIn("Windows AMD64：已完成 / \033[1;31m失败\033[0m", output)


if __name__ == "__main__":
    unittest.main()
