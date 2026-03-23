import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import count_nonempty_lines


class HiddenTests(unittest.TestCase):
    def test_tabs(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("\t\nvalue\n")
            name = handle.name
        try:
            self.assertEqual(count_nonempty_lines(name), 1)
        finally:
            os.remove(name)
