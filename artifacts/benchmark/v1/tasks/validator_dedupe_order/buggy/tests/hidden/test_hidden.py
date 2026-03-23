import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dedupe_tags


class HiddenTests(unittest.TestCase):
    def test_order(self):
        self.assertEqual(dedupe_tags(["c", "b", "c", "a"]), ["c", "b", "a"])
