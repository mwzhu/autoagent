import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_rows


class VisibleTests(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(parse_rows("a\n#skip\nb"), ["a", "b"])

    def test_indented_comment(self):
        self.assertEqual(parse_rows("a\n  #skip\n b "), ["a", " b "])
