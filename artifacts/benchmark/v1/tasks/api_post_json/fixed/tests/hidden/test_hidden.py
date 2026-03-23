import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import create_item


class Session:
    def __init__(self):
        self.last_kwargs = None

    def post(self, url, **kwargs):
        self.last_kwargs = kwargs
        return kwargs


class HiddenTests(unittest.TestCase):
    def test_no_data(self):
        session = Session()
        create_item(session, "https://api", {"x": 1})
        self.assertNotIn("data", session.last_kwargs)
