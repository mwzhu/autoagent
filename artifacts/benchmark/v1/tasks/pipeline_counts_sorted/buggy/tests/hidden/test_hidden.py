import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import summarize_counts


class HiddenTests(unittest.TestCase):
    def test_tie_breaker(self):
        self.assertEqual(summarize_counts(["b", "a"]), [("a", 1), ("b", 1)])
