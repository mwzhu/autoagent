import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dedupe_tags


class VisibleTests(unittest.TestCase):
    def test_unique(self):
        self.assertEqual(dedupe_tags(["b", "a", "b"]), ["b", "a"])
