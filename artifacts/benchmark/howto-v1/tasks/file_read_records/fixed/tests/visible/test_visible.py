import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import read_records


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("a\nb\n")
            name = handle.name
        try:
            self.assertEqual(read_records(name), ["a", "b"])
        finally:
            os.remove(name)
