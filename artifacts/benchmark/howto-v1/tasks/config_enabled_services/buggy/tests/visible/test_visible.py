import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import enabled_services


class VisibleTests(unittest.TestCase):
    def test_string(self):
        self.assertEqual(enabled_services({"enabled": "api,worker"}), ["api", "worker"])

    def test_list(self):
        self.assertEqual(enabled_services({"enabled": ["api", "worker"]}), ["api", "worker"])
