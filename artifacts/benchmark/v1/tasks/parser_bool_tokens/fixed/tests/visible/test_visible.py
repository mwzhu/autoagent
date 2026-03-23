import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_bools


class VisibleTests(unittest.TestCase):
    def test_true_false(self):
        self.assertEqual(parse_bools("true,false"), [True, False])

    def test_case(self):
        self.assertEqual(parse_bools("TRUE, false"), [True, False])
