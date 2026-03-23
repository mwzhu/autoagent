import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_summary


class VisibleTests(unittest.TestCase):
    def test_output(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
        try:
            write_summary(name, {"b": 2, "a": 1})
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a:1\nb:2\n")
        finally:
            os.remove(name)
