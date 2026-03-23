import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_tokens


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_tokens("a;b;c"), ["a", "b", "c"])

    def test_blanks(self):
        self.assertEqual(split_tokens("a; ;c"), ["a", "c"])
