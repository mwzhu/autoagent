import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import reset_state


class HiddenTests(unittest.TestCase):
    def test_errors_cleared(self):
        state = {"status": "running", "errors": ["x"]}
        self.assertEqual(reset_state(state)["errors"], [])
