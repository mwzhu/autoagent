import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import greet_main


class HiddenTests(unittest.TestCase):
    def test_missing_again(self):
        self.assertEqual(greet_main([]), 2)
