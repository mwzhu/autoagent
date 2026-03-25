import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_email


class HiddenTests(unittest.TestCase):
    def test_preserve_local(self):
        self.assertEqual(normalize_email(" Abc@EXAMPLE.COM "), "Abc@example.com")
