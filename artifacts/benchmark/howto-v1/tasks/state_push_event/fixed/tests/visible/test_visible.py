import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import push_event


class VisibleTests(unittest.TestCase):
    def test_single_call(self):
        self.assertEqual(push_event("a"), ["a"])

    def test_independent_calls(self):
        push_event("first")
        self.assertEqual(push_event("second"), ["second"])
