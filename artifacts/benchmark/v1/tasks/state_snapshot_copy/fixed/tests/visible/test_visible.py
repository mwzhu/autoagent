import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import snapshot


class VisibleTests(unittest.TestCase):
    def test_equal(self):
        state = {"a": 1}
        self.assertEqual(snapshot(state), {"a": 1})

    def test_copy(self):
        state = {"a": 1}
        snap = snapshot(state)
        snap["a"] = 2
        self.assertEqual(state["a"], 1)
