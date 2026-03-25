import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import greet_main


class VisibleTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(greet_main(["sam"]), "hello sam")

    def test_missing(self):
        self.assertEqual(greet_main([]), 2)
