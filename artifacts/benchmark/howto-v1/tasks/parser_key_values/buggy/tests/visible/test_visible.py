import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_mapping


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_mapping("a=1\nb=2"), {"a": "1", "b": "2"})

    def test_spaces(self):
        self.assertEqual(parse_mapping("a = 1\n b = 2 "), {"a": "1", "b": "2"})
