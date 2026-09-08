"""Offline checks for terminal progress refresh and log fallback."""
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "wheels", Path(__file__).resolve().parents[1] / "scripts/build_wheels_github.py")
wheels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wheels)


class ProgressTest(unittest.TestCase):
    def display(self, terminal=True):
        stream = io.StringIO()
        stream.isatty = lambda: terminal
        with mock.patch.object(wheels.sys, "stdout", stream), mock.patch.dict(
                wheels.os.environ, {"TERM": "xterm", "WT_SESSION": "test"}, clear=True):
            return wheels.ProgressDisplay(), stream

    def test_replaces_previous_block_and_preserves_final_details(self):
        display, stream = self.display()
        with mock.patch.object(wheels.shutil, "get_terminal_size", return_value=os.terminal_size((30, 20))):
            display.update("状态\n平台一\n平台二")
            display.update("状态\n平台一")
            display.update("失败\nhttps://github.com/" + "x" * 100, final=True)
        self.assertIn("\033[3A\r\033[J状态\n平台一\n", stream.getvalue())
        self.assertIn("\033[2A\r\033[J失败\nhttps://github.com/" + "x" * 100, stream.getvalue())
        self.assertTrue(stream.getvalue().endswith("\n"))
        self.assertEqual(display.rows, 0)

    def test_redirect_and_dumb_terminal_are_plain_logs(self):
        display, stream = self.display(False)
        display.update("first")
        display.update("second", final=True)
        self.assertEqual(stream.getvalue(), "first\nsecond\n")
        with mock.patch.object(wheels.sys, "stdout", stream), mock.patch.dict(
                wheels.os.environ, {"TERM": "dumb"}):
            stream.isatty = lambda: True
            self.assertFalse(wheels.ProgressDisplay().live)

    def test_chinese_width_and_colors(self):
        self.assertEqual(wheels.ProgressDisplay.clip("\033[1;32m中文状态\033[0m", 6),
                         "\033[1;32m中文…\033[0m")
        self.assertEqual(wheels.ProgressDisplay.clip("e\u0301abc", 10), "e\u0301abc")

    def test_resize_does_not_move_into_unrelated_output(self):
        display, stream = self.display()
        with mock.patch.object(wheels.shutil, "get_terminal_size", side_effect=[
                os.terminal_size((80, 24)), os.terminal_size((40, 10))]):
            display.update("old")
            display.update("new")
        self.assertEqual(stream.getvalue(), "old\nnew\n")

    def test_failed_run_keeps_final_status_before_error(self):
        display, stream = self.display()
        run = {"path": ".github/workflows/build-wheels.yml", "status": "completed",
               "conclusion": "failure"}
        with mock.patch.object(wheels, "ProgressDisplay", return_value=display), \
                mock.patch.object(wheels.sys, "stdout", stream), \
                mock.patch.object(wheels, "api", return_value=run), \
                mock.patch.object(wheels, "fetch_jobs", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "构建未成功"):
                wheels.wait_for_run("owner/repo", 1, 100, 10)
        self.assertIn("构建状态：已完成 /", stream.getvalue())
        self.assertIn("unavailable", stream.getvalue())
        self.assertEqual(display.rows, 0)


if __name__ == "__main__":
    unittest.main()
