import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import load_mode


class VisibleTests(unittest.TestCase):
    def test_string(self):
        self.assertEqual(load_mode({"mode": "DEV"}), "dev")

    def test_none(self):
        self.assertEqual(load_mode({"mode": None}), "prod")
