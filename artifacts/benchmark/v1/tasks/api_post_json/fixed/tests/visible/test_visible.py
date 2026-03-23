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


class VisibleTests(unittest.TestCase):
    def test_post(self):
        session = Session()
        create_item(session, "https://api", {"x": 1})
        self.assertIn("json", session.last_kwargs)
