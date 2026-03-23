import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_fields


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_fields("a|b"), ["a", "b"])

    def test_blank(self):
        self.assertEqual(split_fields("a| |b"), ["a", "b"])
