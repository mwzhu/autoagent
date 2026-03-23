import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import validate_age


class HiddenTests(unittest.TestCase):
    def test_out_of_range(self):
        self.assertFalse(validate_age("131"))
