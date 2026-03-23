import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dispatch


class VisibleTests(unittest.TestCase):
    def test_known(self):
        self.assertEqual(dispatch(["status"]), "ok")

    def test_case(self):
        self.assertEqual(dispatch(["STATUS"]), "ok")
