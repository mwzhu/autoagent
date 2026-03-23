import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import extract_items


class VisibleTests(unittest.TestCase):
    def test_present(self):
        self.assertEqual(extract_items({"data": {"items": [1, 2]}}), [1, 2])

    def test_missing(self):
        self.assertEqual(extract_items({}), [])
