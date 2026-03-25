import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dispatch


class HiddenTests(unittest.TestCase):
    def test_case(self):
        self.assertEqual(dispatch(["STATUS"]), "ok")
