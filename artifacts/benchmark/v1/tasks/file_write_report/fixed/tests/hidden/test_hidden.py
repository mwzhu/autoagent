import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_report


class HiddenTests(unittest.TestCase):
    def test_deep_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c", "report.txt")
            write_report(path, "x")
            self.assertTrue(os.path.exists(path))
