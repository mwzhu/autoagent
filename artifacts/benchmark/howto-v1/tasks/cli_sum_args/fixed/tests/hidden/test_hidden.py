import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import sum_main


class HiddenTests(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(sum_main(["tool", "-1", "2"]), 1)
