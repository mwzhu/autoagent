import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import sum_main


class VisibleTests(unittest.TestCase):
    def test_numbers_only(self):
        self.assertEqual(sum_main(["1", "2", "3"]), 6)

    def test_program_name(self):
        self.assertEqual(sum_main(["prog", "1", "2"]), 3)
