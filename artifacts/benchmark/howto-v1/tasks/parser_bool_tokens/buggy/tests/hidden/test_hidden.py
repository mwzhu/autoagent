import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_bools


class HiddenTests(unittest.TestCase):
    def test_yes_and_one(self):
        self.assertEqual(parse_bools("yes,1,no"), [True, True, False])
