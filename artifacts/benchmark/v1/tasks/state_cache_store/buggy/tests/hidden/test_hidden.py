import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_or_create


class HiddenTests(unittest.TestCase):
    def test_cached(self):
        cache = {}
        get_or_create(cache, "x", lambda: 1)
        self.assertEqual(get_or_create(cache, "x", lambda: 2), 1)
