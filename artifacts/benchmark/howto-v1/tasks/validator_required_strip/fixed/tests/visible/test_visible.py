import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import require_fields


class VisibleTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(require_fields({"name": ""}, ["name"]), ["name"])

    def test_whitespace(self):
        self.assertEqual(require_fields({"name": "   "}, ["name"]), ["name"])
