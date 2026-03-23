import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_email


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(normalize_email("a@EXAMPLE.COM"), "a@example.com")

    def test_strip(self):
        self.assertEqual(normalize_email(" a@EXAMPLE.COM "), "a@example.com")
