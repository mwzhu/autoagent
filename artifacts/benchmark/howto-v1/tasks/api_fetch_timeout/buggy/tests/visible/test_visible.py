import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import fetch_user


class Session:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return {"url": url, "timeout": timeout}


class VisibleTests(unittest.TestCase):
    def test_url(self):
        session = Session()
        fetch_user(session, "https://api", 3)
        self.assertEqual(session.calls[0][0], "https://api/users/3")

    def test_timeout(self):
        session = Session()
        fetch_user(session, "https://api", 3)
        self.assertEqual(session.calls[0][1], 5)
