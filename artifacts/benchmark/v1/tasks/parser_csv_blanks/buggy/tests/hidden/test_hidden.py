import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_csv_ints


class HiddenTests(unittest.TestCase):
    def test_newlines(self):
        self.assertEqual(parse_csv_ints("4,\n ,5"), [4, 5])

    def test_empty(self):
        self.assertEqual(parse_csv_ints(""), [])
