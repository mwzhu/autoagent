import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import build_url


class HiddenTests(unittest.TestCase):
    def test_nested(self):
        self.assertEqual(build_url("https://api/", "v1/users"), "https://api/v1/users")
