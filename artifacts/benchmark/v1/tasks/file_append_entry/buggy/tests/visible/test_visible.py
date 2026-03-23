import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import append_entry


class VisibleTests(unittest.TestCase):
    def test_first_append(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
        try:
            append_entry(name, "a")
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a")
        finally:
            os.remove(name)

    def test_second_append(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
            handle.write("a")
        try:
            append_entry(name, "b")
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a\nb")
        finally:
            os.remove(name)
