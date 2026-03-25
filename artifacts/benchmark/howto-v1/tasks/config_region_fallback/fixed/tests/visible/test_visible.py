import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import resolve_region


class VisibleTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(resolve_region({}), "us-west-1")

    def test_blank(self):
        self.assertEqual(resolve_region({"region": "   "}), "us-west-1")
