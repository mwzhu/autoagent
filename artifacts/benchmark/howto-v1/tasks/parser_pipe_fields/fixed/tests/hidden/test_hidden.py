import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_fields


class HiddenTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(split_fields(" | "), [])
