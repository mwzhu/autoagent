import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import build_url


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(build_url("https://api", "users"), "https://api/users")

    def test_slashes(self):
        self.assertEqual(build_url("https://api/", "/users"), "https://api/users")
