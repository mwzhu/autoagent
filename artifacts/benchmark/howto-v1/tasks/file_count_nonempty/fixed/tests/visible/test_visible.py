import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import count_nonempty_lines


class VisibleTests(unittest.TestCase):
    def test_simple(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("a\n\n b \n")
            name = handle.name
        try:
            self.assertEqual(count_nonempty_lines(name), 2)
        finally:
            os.remove(name)
