import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_tokens


class HiddenTests(unittest.TestCase):
    def test_trailing(self):
        self.assertEqual(split_tokens("a; ; "), ["a"])
