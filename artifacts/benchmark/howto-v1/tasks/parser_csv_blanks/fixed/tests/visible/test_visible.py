import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_csv_ints


class VisibleTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_csv_ints("1,2,3"), [1, 2, 3])

    def test_whitespace_blank(self):
        self.assertEqual(parse_csv_ints("1, ,2"), [1, 2])
