import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_mapping


class HiddenTests(unittest.TestCase):
    def test_blank_lines(self):
        text = "\na = 1\n\n c = 3 \n"
        self.assertEqual(parse_mapping(text), {"a": "1", "c": "3"})
