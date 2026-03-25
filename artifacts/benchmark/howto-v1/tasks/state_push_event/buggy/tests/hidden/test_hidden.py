import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import push_event


class HiddenTests(unittest.TestCase):
    def test_repeated_calls(self):
        push_event("first")
        push_event("second")
        self.assertEqual(push_event("third"), ["third"])
