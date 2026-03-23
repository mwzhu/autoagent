import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_report


class VisibleTests(unittest.TestCase):
    def test_nested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "reports", "out.txt")
            write_report(path, "done")
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "done")
