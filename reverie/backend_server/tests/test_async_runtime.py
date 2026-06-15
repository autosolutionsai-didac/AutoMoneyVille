import asyncio
import sys
import time
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from persona.prompt_template.claude_structure import _run_async


class AsyncRuntimeTests(unittest.TestCase):
    def test_run_async_timeout_returns_control_quickly(self):
        started = time.monotonic()

        with self.assertRaises(asyncio.TimeoutError):
            _run_async(asyncio.sleep(5), timeout=0.01)

        self.assertLess(time.monotonic() - started, 1)


if __name__ == "__main__":
    unittest.main()
