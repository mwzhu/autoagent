import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import upper_main


class VisibleTests(unittest.TestCase):
    def test_arg(self):
        self.assertEqual(upper_main(["abc"], "ignored"), "ABC")

    def test_stdin(self):
        self.assertEqual(upper_main([], "hello"), "HELLO")
