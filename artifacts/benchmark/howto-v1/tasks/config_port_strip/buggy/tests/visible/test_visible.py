import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_port


class VisibleTests(unittest.TestCase):
    def test_int(self):
        self.assertEqual(get_port({"port": 9000}), 9000)

    def test_blank(self):
        self.assertEqual(get_port({"port": ""}), 8080)
