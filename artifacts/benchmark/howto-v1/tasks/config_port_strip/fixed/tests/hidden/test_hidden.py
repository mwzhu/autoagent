import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_port


class HiddenTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(get_port({"port": "   "}), 8080)
