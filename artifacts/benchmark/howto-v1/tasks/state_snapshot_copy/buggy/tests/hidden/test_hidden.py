import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import snapshot


class HiddenTests(unittest.TestCase):
    def test_add_key(self):
        state = {"a": 1}
        snap = snapshot(state)
        snap["b"] = 2
        self.assertNotIn("b", state)
