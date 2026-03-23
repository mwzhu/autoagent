import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import validate_age


class VisibleTests(unittest.TestCase):
    def test_int(self):
        self.assertTrue(validate_age(10))

    def test_string(self):
        self.assertTrue(validate_age("10"))
