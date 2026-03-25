import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import upper_main


class HiddenTests(unittest.TestCase):
    def test_multiline(self):
        self.assertEqual(upper_main([], "a\nb"), "A\nB")
