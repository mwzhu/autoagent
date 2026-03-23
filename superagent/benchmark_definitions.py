"""Generated benchmark definitions."""

from __future__ import annotations

from typing import Dict, List


def _task(
    task_id: str,
    repo_id: str,
    category: str,
    split: str,
    difficulty: int,
    prompt: str,
    buggy_source: str,
    fixed_source: str,
    visible_tests: str,
    hidden_tests: str,
    required_capabilities: List[str] = None,
    min_test_budget: int = 1,
    min_file_read_budget: int = 1,
) -> Dict[str, object]:
    return {
        "task_id": task_id,
        "repo_id": repo_id,
        "category": category,
        "split": split,
        "difficulty": difficulty,
        "prompt": prompt,
        "buggy_source": buggy_source.strip() + "\n",
        "fixed_source": fixed_source.strip() + "\n",
        "visible_tests": visible_tests.strip() + "\n",
        "hidden_tests": hidden_tests.strip() + "\n",
        "required_capabilities": list(required_capabilities or []),
        "min_test_budget": min_test_budget,
        "min_file_read_budget": min_file_read_budget,
    }


DEFAULT_TASK_DEFINITIONS = [
    _task(
        "parser_csv_blanks",
        "parser_lab",
        "parsing",
        "train",
        1,
        "Fix src/app.py so parse_csv_ints skips blank comma-separated fields that only contain whitespace.",
        """
def parse_csv_ints(text):
    return [int(part.strip()) for part in text.split(",") if part]
        """,
        """
def parse_csv_ints(text):
    return [int(part.strip()) for part in text.split(",") if part.strip()]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_csv_ints


class VisibleTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_csv_ints("1,2,3"), [1, 2, 3])

    def test_whitespace_blank(self):
        self.assertEqual(parse_csv_ints("1, ,2"), [1, 2])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_csv_ints


class HiddenTests(unittest.TestCase):
    def test_newlines(self):
        self.assertEqual(parse_csv_ints("4,\\n ,5"), [4, 5])

    def test_empty(self):
        self.assertEqual(parse_csv_ints(""), [])
        """,
        ["self_check"],
    ),
    _task(
        "parser_bool_tokens",
        "parser_lab",
        "parsing",
        "train",
        2,
        "Fix src/app.py so parse_bools handles case-insensitive boolean tokens and trims whitespace.",
        """
def parse_bools(text):
    return [token == "true" for token in text.split(",")]
        """,
        """
def parse_bools(text):
    truthy = {"true", "yes", "1"}
    return [token.strip().lower() in truthy for token in text.split(",") if token.strip()]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_bools


class VisibleTests(unittest.TestCase):
    def test_true_false(self):
        self.assertEqual(parse_bools("true,false"), [True, False])

    def test_case(self):
        self.assertEqual(parse_bools("TRUE, false"), [True, False])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_bools


class HiddenTests(unittest.TestCase):
    def test_yes_and_one(self):
        self.assertEqual(parse_bools("yes,1,no"), [True, True, False])
        """,
        ["planning"],
    ),
    _task(
        "parser_key_values",
        "parser_lab",
        "parsing",
        "train",
        2,
        "Fix src/app.py so parse_mapping ignores blank lines and trims keys and values around '='.",
        """
def parse_mapping(text):
    result = {}
    for line in text.splitlines():
        if not line:
            continue
        key, value = line.split("=")
        result[key] = value
    return result
        """,
        """
def parse_mapping(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_mapping


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_mapping("a=1\\nb=2"), {"a": "1", "b": "2"})

    def test_spaces(self):
        self.assertEqual(parse_mapping("a = 1\\n b = 2 "), {"a": "1", "b": "2"})
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_mapping


class HiddenTests(unittest.TestCase):
    def test_blank_lines(self):
        text = "\\na = 1\\n\\n c = 3 \\n"
        self.assertEqual(parse_mapping(text), {"a": "1", "c": "3"})
        """,
        ["self_check"],
        min_file_read_budget=2,
    ),
    _task(
        "parser_semicolon_tokens",
        "parser_lab",
        "parsing",
        "train",
        1,
        "Fix src/app.py so split_tokens drops blank semicolon-separated tokens that only contain whitespace.",
        """
def split_tokens(text):
    return [token.strip() for token in text.split(";") if token]
        """,
        """
def split_tokens(text):
    return [token.strip() for token in text.split(";") if token.strip()]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_tokens


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_tokens("a;b;c"), ["a", "b", "c"])

    def test_blanks(self):
        self.assertEqual(split_tokens("a; ;c"), ["a", "c"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_tokens


class HiddenTests(unittest.TestCase):
    def test_trailing(self):
        self.assertEqual(split_tokens("a; ; "), ["a"])
        """,
        ["self_check"],
    ),
    _task(
        "config_port_strip",
        "config_loader",
        "data_validation",
        "train",
        1,
        "Fix src/app.py so get_port falls back to the default when the config value is blank or whitespace, and trims string values before converting them.",
        """
def get_port(config):
    value = config.get("port", 8080)
    if value == "":
        return 0
    return int(value)
        """,
        """
def get_port(config):
    value = config.get("port", 8080)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return 8080
    return int(value)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_port


class VisibleTests(unittest.TestCase):
    def test_int(self):
        self.assertEqual(get_port({"port": 9000}), 9000)

    def test_blank(self):
        self.assertEqual(get_port({"port": ""}), 8080)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_port


class HiddenTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(get_port({"port": "   "}), 8080)
        """,
        ["self_check"],
    ),
    _task(
        "config_enabled_services",
        "config_loader",
        "parsing",
        "train",
        2,
        "Fix src/app.py so enabled_services returns trimmed service names instead of splitting a string into characters.",
        """
def enabled_services(config):
    return list(config.get("enabled", ""))
        """,
        """
def enabled_services(config):
    raw = config.get("enabled", [])
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [str(part).strip() for part in raw if str(part).strip()]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import enabled_services


class VisibleTests(unittest.TestCase):
    def test_string(self):
        self.assertEqual(enabled_services({"enabled": "api,worker"}), ["api", "worker"])

    def test_list(self):
        self.assertEqual(enabled_services({"enabled": ["api", "worker"]}), ["api", "worker"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import enabled_services


class HiddenTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(enabled_services({"enabled": " api, , worker "}), ["api", "worker"])
        """,
        ["planning"],
    ),
    _task(
        "config_mode_none",
        "config_loader",
        "data_validation",
        "guard",
        2,
        "Fix src/app.py so load_mode handles None values by falling back to 'prod'.",
        """
def load_mode(config):
    return config.get("mode", "prod").lower()
        """,
        """
def load_mode(config):
    mode = config.get("mode") or "prod"
    return str(mode).lower()
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import load_mode


class VisibleTests(unittest.TestCase):
    def test_string(self):
        self.assertEqual(load_mode({"mode": "DEV"}), "dev")

    def test_none(self):
        self.assertEqual(load_mode({"mode": None}), "prod")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import load_mode


class HiddenTests(unittest.TestCase):
    def test_none(self):
        self.assertEqual(load_mode({"mode": None}), "prod")
        """,
        ["self_check"],
    ),
    _task(
        "config_region_fallback",
        "config_loader",
        "data_validation",
        "holdout",
        3,
        "Fix src/app.py so resolve_region falls back to the default when the config value is blank or whitespace.",
        """
def resolve_region(config):
    return config.get("region", "us-west-1")
        """,
        """
def resolve_region(config):
    region = config.get("region", "us-west-1")
    if isinstance(region, str) and not region.strip():
        return "us-west-1"
    return region
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import resolve_region


class VisibleTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(resolve_region({}), "us-west-1")

    def test_blank(self):
        self.assertEqual(resolve_region({"region": "   "}), "us-west-1")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import resolve_region


class HiddenTests(unittest.TestCase):
    def test_blank(self):
        self.assertEqual(resolve_region({"region": "   "}), "us-west-1")
        """,
        ["planning"],
    ),
    _task(
        "file_write_report",
        "file_tools",
        "file_io",
        "train",
        2,
        "Fix src/app.py so write_report creates parent directories before writing the file.",
        """
from pathlib import Path


def write_report(path, text):
    Path(path).write_text(text, encoding="utf-8")
        """,
        """
from pathlib import Path


def write_report(path, text):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_report


class VisibleTests(unittest.TestCase):
    def test_nested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "reports", "out.txt")
            write_report(path, "done")
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "done")
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_report


class HiddenTests(unittest.TestCase):
    def test_deep_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c", "report.txt")
            write_report(path, "x")
            self.assertTrue(os.path.exists(path))
        """,
        ["planning"],
    ),
    _task(
        "file_count_nonempty",
        "file_tools",
        "file_io",
        "train",
        1,
        "Fix src/app.py so count_nonempty_lines skips lines that only contain whitespace.",
        """
def count_nonempty_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line)
        """,
        """
def count_nonempty_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import count_nonempty_lines


class VisibleTests(unittest.TestCase):
    def test_simple(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("a\\n\\n b \\n")
            name = handle.name
        try:
            self.assertEqual(count_nonempty_lines(name), 2)
        finally:
            os.remove(name)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import count_nonempty_lines


class HiddenTests(unittest.TestCase):
    def test_tabs(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("\\t\\nvalue\\n")
            name = handle.name
        try:
            self.assertEqual(count_nonempty_lines(name), 1)
        finally:
            os.remove(name)
        """,
        ["self_check"],
    ),
    _task(
        "file_read_records",
        "file_tools",
        "file_io",
        "guard",
        1,
        "Fix src/app.py so read_records strips trailing newlines from each record.",
        """
def read_records(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readlines()
        """,
        """
def read_records(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [line.rstrip("\\n") for line in handle]
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import read_records


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("a\\nb\\n")
            name = handle.name
        try:
            self.assertEqual(read_records(name), ["a", "b"])
        finally:
            os.remove(name)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import read_records


class HiddenTests(unittest.TestCase):
    def test_blank(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("a\\n\\n")
            name = handle.name
        try:
            self.assertEqual(read_records(name), ["a", ""])
        finally:
            os.remove(name)
        """,
        ["self_check"],
    ),
    _task(
        "file_append_entry",
        "file_tools",
        "file_io",
        "holdout",
        2,
        "Fix src/app.py so append_entry always writes one newline per appended entry when the file already exists.",
        """
def append_entry(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
        """,
        """
def append_entry(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        if handle.tell() > 0:
            handle.write("\\n")
        handle.write(text)
        """,
        """
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
                self.assertEqual(handle.read(), "a\\nb")
        finally:
            os.remove(name)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import append_entry


class HiddenTests(unittest.TestCase):
    def test_second_append(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
            handle.write("a")
        try:
            append_entry(name, "b")
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a\\nb")
        finally:
            os.remove(name)
        """,
        ["planning"],
    ),
    _task(
        "cli_sum_args",
        "cli_tools",
        "cli_behavior",
        "train",
        1,
        "Fix src/app.py so sum_main ignores the program name when argv includes it.",
        """
def sum_main(argv):
    return sum(int(value) for value in argv)
        """,
        """
def sum_main(argv):
    values = argv[1:] if argv and not str(argv[0]).lstrip("-").isdigit() else argv
    return sum(int(value) for value in values)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import sum_main


class VisibleTests(unittest.TestCase):
    def test_numbers_only(self):
        self.assertEqual(sum_main(["1", "2", "3"]), 6)

    def test_program_name(self):
        self.assertEqual(sum_main(["prog", "1", "2"]), 3)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import sum_main


class HiddenTests(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(sum_main(["tool", "-1", "2"]), 1)
        """,
        ["self_check"],
    ),
    _task(
        "cli_missing_name",
        "cli_tools",
        "cli_behavior",
        "train",
        2,
        "Fix src/app.py so greet_main returns exit code 2 when the name argument is missing.",
        """
def greet_main(argv):
    if not argv:
        return 0
    return "hello " + argv[0]
        """,
        """
def greet_main(argv):
    if not argv:
        return 2
    return "hello " + argv[0]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import greet_main


class VisibleTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(greet_main(["sam"]), "hello sam")

    def test_missing(self):
        self.assertEqual(greet_main([]), 2)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import greet_main


class HiddenTests(unittest.TestCase):
    def test_missing_again(self):
        self.assertEqual(greet_main([]), 2)
        """,
        ["planning"],
    ),
    _task(
        "cli_upper_stdin",
        "cli_tools",
        "cli_behavior",
        "train",
        2,
        "Fix src/app.py so upper_main falls back to stdin when no argument is provided.",
        """
def upper_main(argv, stdin):
    if not argv:
        return ""
    return argv[0].upper()
        """,
        """
def upper_main(argv, stdin):
    if not argv:
        return stdin.upper()
    return argv[0].upper()
        """,
        """
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
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import upper_main


class HiddenTests(unittest.TestCase):
    def test_multiline(self):
        self.assertEqual(upper_main([], "a\\nb"), "A\\nB")
        """,
        ["decomposition"],
    ),
    _task(
        "cli_dispatch_case",
        "cli_tools",
        "cli_behavior",
        "guard",
        2,
        "Fix src/app.py so dispatch handles command names case-insensitively.",
        """
def dispatch(argv):
    command = argv[0]
    if command == "status":
        return "ok"
    if command == "reset":
        return "reset"
    return "unknown"
        """,
        """
def dispatch(argv):
    command = argv[0].lower()
    if command == "status":
        return "ok"
    if command == "reset":
        return "reset"
    return "unknown"
        """,
        """
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
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dispatch


class HiddenTests(unittest.TestCase):
    def test_case(self):
        self.assertEqual(dispatch(["STATUS"]), "ok")
        """,
        ["planning"],
    ),
    _task(
        "state_push_event",
        "state_store",
        "state_handling",
        "train",
        2,
        "Fix src/app.py so push_event does not reuse a shared default list between calls.",
        """
def push_event(event, seen=[]):
    seen.append(event)
    return list(seen)
        """,
        """
def push_event(event, seen=None):
    seen = list(seen or [])
    seen.append(event)
    return seen
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import push_event


class VisibleTests(unittest.TestCase):
    def test_single_call(self):
        self.assertEqual(push_event("a"), ["a"])

    def test_independent_calls(self):
        push_event("first")
        self.assertEqual(push_event("second"), ["second"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import push_event


class HiddenTests(unittest.TestCase):
    def test_repeated_calls(self):
        push_event("first")
        push_event("second")
        self.assertEqual(push_event("third"), ["third"])
        """,
        ["self_check"],
    ),
    _task(
        "state_snapshot_copy",
        "state_store",
        "state_handling",
        "train",
        2,
        "Fix src/app.py so snapshot returns a copy of the state dictionary instead of the original object.",
        """
def snapshot(state):
    return state
        """,
        """
def snapshot(state):
    return dict(state)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import snapshot


class VisibleTests(unittest.TestCase):
    def test_equal(self):
        state = {"a": 1}
        self.assertEqual(snapshot(state), {"a": 1})

    def test_copy(self):
        state = {"a": 1}
        snap = snapshot(state)
        snap["a"] = 2
        self.assertEqual(state["a"], 1)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import snapshot


class HiddenTests(unittest.TestCase):
    def test_add_key(self):
        state = {"a": 1}
        snap = snapshot(state)
        snap["b"] = 2
        self.assertNotIn("b", state)
        """,
        ["decomposition"],
    ),
    _task(
        "state_reset_errors",
        "state_store",
        "state_handling",
        "guard",
        2,
        "Fix src/app.py so reset_state clears the nested errors list as well as the top-level status.",
        """
def reset_state(state):
    state["status"] = "idle"
    return state
        """,
        """
def reset_state(state):
    state["status"] = "idle"
    if "errors" in state:
        state["errors"] = []
    return state
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import reset_state


class VisibleTests(unittest.TestCase):
    def test_status(self):
        state = {"status": "running", "errors": ["x"]}
        self.assertEqual(reset_state(state)["status"], "idle")

    def test_errors_cleared(self):
        state = {"status": "running", "errors": ["x"]}
        self.assertEqual(reset_state(state)["errors"], [])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import reset_state


class HiddenTests(unittest.TestCase):
    def test_errors_cleared(self):
        state = {"status": "running", "errors": ["x"]}
        self.assertEqual(reset_state(state)["errors"], [])
        """,
        ["planning"],
    ),
    _task(
        "state_cache_store",
        "state_store",
        "state_handling",
        "holdout",
        3,
        "Fix src/app.py so get_or_create stores the computed value in the cache before returning it.",
        """
def get_or_create(cache, key, factory):
    if key in cache:
        return cache[key]
    return factory()
        """,
        """
def get_or_create(cache, key, factory):
    if key in cache:
        return cache[key]
    value = factory()
    cache[key] = value
    return value
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_or_create


class VisibleTests(unittest.TestCase):
    def test_create(self):
        cache = {}
        self.assertEqual(get_or_create(cache, "x", lambda: 1), 1)

    def test_cached(self):
        cache = {}
        get_or_create(cache, "x", lambda: 1)
        self.assertEqual(get_or_create(cache, "x", lambda: 2), 1)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_or_create


class HiddenTests(unittest.TestCase):
    def test_cached(self):
        cache = {}
        get_or_create(cache, "x", lambda: 1)
        self.assertEqual(get_or_create(cache, "x", lambda: 2), 1)
        """,
        ["planning"],
    ),
    _task(
        "api_build_url",
        "api_client",
        "api_client_mocking",
        "train",
        2,
        "Fix src/app.py so build_url joins base URLs and paths with exactly one slash.",
        """
def build_url(base, path):
    return base + "/" + path
        """,
        """
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import build_url


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(build_url("https://api", "users"), "https://api/users")

    def test_slashes(self):
        self.assertEqual(build_url("https://api/", "/users"), "https://api/users")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import build_url


class HiddenTests(unittest.TestCase):
    def test_nested(self):
        self.assertEqual(build_url("https://api/", "v1/users"), "https://api/v1/users")
        """,
        ["self_check"],
    ),
    _task(
        "api_fetch_timeout",
        "api_client",
        "api_client_mocking",
        "train",
        3,
        "Fix src/app.py so fetch_user passes a timeout to the session.get call.",
        """
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def fetch_user(session, base_url, user_id):
    return session.get(build_url(base_url, "/users/" + str(user_id)))
        """,
        """
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def fetch_user(session, base_url, user_id):
    return session.get(build_url(base_url, "/users/" + str(user_id)), timeout=5)
        """,
        """
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
        """,
        """
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


class HiddenTests(unittest.TestCase):
    def test_timeout(self):
        session = Session()
        fetch_user(session, "https://api", 3)
        self.assertEqual(session.calls[0][1], 5)
        """,
        ["planning"],
    ),
    _task(
        "api_post_json",
        "api_client",
        "api_client_mocking",
        "guard",
        3,
        "Fix src/app.py so create_item posts JSON via the json= keyword instead of data=.",
        """
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def create_item(session, base_url, payload):
    return session.post(build_url(base_url, "/items"), data=payload)
        """,
        """
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def create_item(session, base_url, payload):
    return session.post(build_url(base_url, "/items"), json=payload)
        """,
        """
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
        """,
        """
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
        """,
        ["decomposition"],
        min_file_read_budget=2,
    ),
    _task(
        "api_extract_items",
        "api_client",
        "api_client_mocking",
        "holdout",
        2,
        "Fix src/app.py so extract_items returns an empty list when the response has no data key.",
        """
def extract_items(response):
    return response["data"]["items"]
        """,
        """
def extract_items(response):
    return response.get("data", {}).get("items", [])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import extract_items


class VisibleTests(unittest.TestCase):
    def test_present(self):
        self.assertEqual(extract_items({"data": {"items": [1, 2]}}), [1, 2])

    def test_missing(self):
        self.assertEqual(extract_items({}), [])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import extract_items


class HiddenTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(extract_items({}), [])
        """,
        ["planning"],
    ),
    _task(
        "validator_email_strip",
        "validator_suite",
        "data_validation",
        "train",
        1,
        "Fix src/app.py so normalize_email trims whitespace before normalizing the value.",
        """
def normalize_email(value):
    local, domain = value.split("@")
    return local + "@" + domain.lower()
        """,
        """
def normalize_email(value):
    value = value.strip()
    local, domain = value.split("@")
    return local + "@" + domain.lower()
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_email


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(normalize_email("a@EXAMPLE.COM"), "a@example.com")

    def test_strip(self):
        self.assertEqual(normalize_email(" a@EXAMPLE.COM "), "a@example.com")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_email


class HiddenTests(unittest.TestCase):
    def test_preserve_local(self):
        self.assertEqual(normalize_email(" Abc@EXAMPLE.COM "), "Abc@example.com")
        """,
        ["self_check"],
    ),
    _task(
        "validator_age_numeric",
        "validator_suite",
        "data_validation",
        "train",
        2,
        "Fix src/app.py so validate_age accepts numeric strings by converting them to integers before comparison.",
        """
def validate_age(value):
    return 0 <= value <= 130
        """,
        """
def validate_age(value):
    if isinstance(value, str):
        value = int(value.strip())
    return 0 <= value <= 130
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import validate_age


class VisibleTests(unittest.TestCase):
    def test_int(self):
        self.assertTrue(validate_age(10))

    def test_string(self):
        self.assertTrue(validate_age("10"))
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import validate_age


class HiddenTests(unittest.TestCase):
    def test_out_of_range(self):
        self.assertFalse(validate_age("131"))
        """,
        ["planning"],
    ),
    _task(
        "validator_dedupe_order",
        "validator_suite",
        "data_validation",
        "guard",
        2,
        "Fix src/app.py so dedupe_tags preserves the original order of tags.",
        """
def dedupe_tags(tags):
    return sorted(set(tags))
        """,
        """
def dedupe_tags(tags):
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dedupe_tags


class VisibleTests(unittest.TestCase):
    def test_unique(self):
        self.assertEqual(dedupe_tags(["b", "a", "b"]), ["b", "a"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import dedupe_tags


class HiddenTests(unittest.TestCase):
    def test_order(self):
        self.assertEqual(dedupe_tags(["c", "b", "c", "a"]), ["c", "b", "a"])
        """,
        ["decomposition"],
    ),
    _task(
        "validator_required_strip",
        "validator_suite",
        "data_validation",
        "holdout",
        2,
        "Fix src/app.py so require_fields treats whitespace-only strings as missing values.",
        """
def require_fields(payload, fields):
    return [field for field in fields if not payload.get(field)]
        """,
        """
def require_fields(payload, fields):
    missing = []
    for field in fields:
        value = payload.get(field)
        if value is None:
            missing.append(field)
        elif isinstance(value, str) and not value.strip():
            missing.append(field)
    return missing
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import require_fields


class VisibleTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(require_fields({"name": ""}, ["name"]), ["name"])

    def test_whitespace(self):
        self.assertEqual(require_fields({"name": "   "}, ["name"]), ["name"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import require_fields


class HiddenTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(require_fields({"name": "   "}, ["name"]), ["name"])
        """,
        ["planning"],
    ),
    _task(
        "pipeline_skip_comments",
        "data_pipeline",
        "parsing",
        "train",
        2,
        "Fix src/app.py so parse_rows skips comment lines even when they begin with whitespace.",
        """
def parse_rows(text):
    return [line for line in text.splitlines() if line and not line.startswith("#")]
        """,
        """
def parse_rows(text):
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_rows


class VisibleTests(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(parse_rows("a\\n#skip\\nb"), ["a", "b"])

    def test_indented_comment(self):
        self.assertEqual(parse_rows("a\\n  #skip\\n b "), ["a", " b "])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_rows


class HiddenTests(unittest.TestCase):
    def test_indented_comment(self):
        self.assertEqual(parse_rows("a\\n  #skip\\n b "), ["a", " b "])
        """,
        ["planning"],
    ),
    _task(
        "pipeline_counts_sorted",
        "data_pipeline",
        "state_handling",
        "train",
        3,
        "Fix src/app.py so summarize_counts returns items sorted by descending count and then by key.",
        """
def summarize_counts(rows):
    counts = {}
    for row in rows:
        counts[row] = counts.get(row, 0) + 1
    return list(counts.items())
        """,
        """
def summarize_counts(rows):
    counts = {}
    for row in rows:
        counts[row] = counts.get(row, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import summarize_counts


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(summarize_counts(["b", "a", "b"]), [("b", 2), ("a", 1)])

    def test_tie_breaker(self):
        self.assertEqual(summarize_counts(["b", "a"]), [("a", 1), ("b", 1)])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import summarize_counts


class HiddenTests(unittest.TestCase):
    def test_tie_breaker(self):
        self.assertEqual(summarize_counts(["b", "a"]), [("a", 1), ("b", 1)])
        """,
        ["decomposition"],
        min_test_budget=2,
    ),
    _task(
        "pipeline_merge_defaults",
        "data_pipeline",
        "state_handling",
        "guard",
        3,
        "Fix src/app.py so merge_config lets explicit values override defaults.",
        """
def merge_config(defaults, overrides):
    result = dict(overrides)
    result.update(defaults)
    return result
        """,
        """
def merge_config(defaults, overrides):
    result = dict(defaults)
    result.update(overrides)
    return result
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_config


class VisibleTests(unittest.TestCase):
    def test_override(self):
        self.assertEqual(merge_config({"a": 1}, {"a": 2})["a"], 2)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_config


class HiddenTests(unittest.TestCase):
    def test_keep_default(self):
        self.assertEqual(merge_config({"a": 1, "b": 2}, {"a": 3})["b"], 2)
        """,
        ["planning"],
    ),
    _task(
        "pipeline_write_summary",
        "data_pipeline",
        "file_io",
        "holdout",
        2,
        "Fix src/app.py so write_summary writes output sorted by key for stable snapshots.",
        """
def write_summary(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        for key, value in counts.items():
            handle.write(f"{key}:{value}\\n")
        """,
        """
def write_summary(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        for key in sorted(counts):
            handle.write(f"{key}:{counts[key]}\\n")
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_summary


class VisibleTests(unittest.TestCase):
    def test_output(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
        try:
            write_summary(name, {"b": 2, "a": 1})
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a:1\\nb:2\\n")
        finally:
            os.remove(name)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import write_summary


class HiddenTests(unittest.TestCase):
    def test_sorted(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
        try:
            write_summary(name, {"b": 2, "a": 1})
            with open(name, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a:1\\nb:2\\n")
        finally:
            os.remove(name)
        """,
        ["planning"],
    ),
    _task(
        "parser_pipe_fields",
        "parser_lab",
        "parsing",
        "train",
        2,
        "Fix src/app.py so split_fields drops blank pipe-delimited fields after trimming.",
        """
def split_fields(text):
    return [field.strip() for field in text.split("|") if field]
        """,
        """
def split_fields(text):
    return [field.strip() for field in text.split("|") if field.strip()]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_fields


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_fields("a|b"), ["a", "b"])

    def test_blank(self):
        self.assertEqual(split_fields("a| |b"), ["a", "b"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import split_fields


class HiddenTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(split_fields(" | "), [])
        """,
        ["self_check"],
    ),
    _task(
        "file_load_settings",
        "file_tools",
        "file_io",
        "train",
        2,
        "Fix src/app.py so load_settings returns an empty dict when the file does not exist.",
        """
import json


def load_settings(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
        """,
        """
import json
import os


def load_settings(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import load_settings


class VisibleTests(unittest.TestCase):
    def test_existing(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write("{\\"a\\": 1}")
            name = handle.name
        try:
            self.assertEqual(load_settings(name), {"a": 1})
        finally:
            os.remove(name)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import load_settings


class HiddenTests(unittest.TestCase):
    def test_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_settings(os.path.join(tmp, "missing.json")), {})
        """,
        ["planning"],
    ),
    _task(
        "cli_csv_output",
        "cli_tools",
        "cli_behavior",
        "train",
        2,
        "Fix src/app.py so render_csv appends a trailing newline after joining rows.",
        """
def render_csv(rows):
    return "\\n".join(",".join(row) for row in rows)
        """,
        """
def render_csv(rows):
    return "\\n".join(",".join(row) for row in rows) + "\\n"
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import render_csv


class VisibleTests(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(render_csv([["a", "b"]]), "a,b\\n")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import render_csv


class HiddenTests(unittest.TestCase):
    def test_multiple_rows(self):
        self.assertEqual(render_csv([["a"], ["b"]]), "a\\nb\\n")
        """,
        ["planning"],
    ),
    _task(
        "state_prune_history",
        "state_store",
        "state_handling",
        "train",
        3,
        "Fix src/app.py so prune_history keeps the most recent items instead of the oldest items.",
        """
def prune_history(values, limit):
    return values[:limit]
        """,
        """
def prune_history(values, limit):
    return values[-limit:]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import prune_history


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(prune_history([1, 2, 3, 4], 2), [3, 4])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import prune_history


class HiddenTests(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(prune_history([1, 2], 2), [1, 2])
        """,
        ["decomposition"],
    ),
    _task(
        "api_headers_merge",
        "api_client",
        "api_client_mocking",
        "train",
        3,
        "Fix src/app.py so merge_headers lets explicit request headers override defaults.",
        """
def merge_headers(defaults, request):
    result = dict(request)
    result.update(defaults)
    return result
        """,
        """
def merge_headers(defaults, request):
    result = dict(defaults)
    result.update(request)
    return result
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_headers


class VisibleTests(unittest.TestCase):
    def test_override(self):
        self.assertEqual(merge_headers({"Auth": "a"}, {"Auth": "b"})["Auth"], "b")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_headers


class HiddenTests(unittest.TestCase):
    def test_keep_default(self):
        self.assertEqual(merge_headers({"Auth": "a", "X": "1"}, {"Auth": "b"})["X"], "1")
        """,
        ["decomposition"],
    ),
    _task(
        "validator_trimmed_codes",
        "validator_suite",
        "data_validation",
        "train",
        2,
        "Fix src/app.py so normalize_codes trims each code before uppercasing it.",
        """
def normalize_codes(codes):
    return [code.upper() for code in codes]
        """,
        """
def normalize_codes(codes):
    return [code.strip().upper() for code in codes]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_codes


class VisibleTests(unittest.TestCase):
    def test_upper(self):
        self.assertEqual(normalize_codes(["ab"]), ["AB"])

    def test_strip(self):
        self.assertEqual(normalize_codes([" ab "]), ["AB"])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import normalize_codes


class HiddenTests(unittest.TestCase):
    def test_multiple(self):
        self.assertEqual(normalize_codes([" a ", "b "]), ["A", "B"])
        """,
        ["self_check"],
    ),
    _task(
        "pipeline_filter_errors",
        "data_pipeline",
        "data_validation",
        "train",
        3,
        "Fix src/app.py so filter_ok removes rows whose status values differ from OK only by case or whitespace.",
        """
def filter_ok(rows):
    return [row for row in rows if row["status"] == "OK"]
        """,
        """
def filter_ok(rows):
    return [row for row in rows if str(row["status"]).strip().upper() == "OK"]
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import filter_ok


class VisibleTests(unittest.TestCase):
    def test_ok(self):
        rows = [{"status": "OK"}, {"status": "ERR"}]
        self.assertEqual(filter_ok(rows), [{"status": "OK"}])
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import filter_ok


class HiddenTests(unittest.TestCase):
    def test_whitespace_case(self):
        rows = [{"status": " ok "}, {"status": "ERR"}]
        self.assertEqual(filter_ok(rows), [{"status": " ok "}])
        """,
        ["planning"],
        min_test_budget=2,
    ),
    _task(
        "config_read_timeout",
        "config_loader",
        "data_validation",
        "guard",
        2,
        "Fix src/app.py so get_timeout coerces string values to integers before returning them.",
        """
def get_timeout(config):
    return config.get("timeout", 30)
        """,
        """
def get_timeout(config):
    value = config.get("timeout", 30)
    if isinstance(value, str):
        value = int(value.strip())
    return value
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_timeout


class VisibleTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(get_timeout({}), 30)
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import get_timeout


class HiddenTests(unittest.TestCase):
    def test_string(self):
        self.assertEqual(get_timeout({"timeout": " 45 "}), 45)
        """,
        ["self_check"],
    ),
    _task(
        "file_safe_remove",
        "file_tools",
        "file_io",
        "guard",
        2,
        "Fix src/app.py so safe_remove ignores missing files instead of raising FileNotFoundError.",
        """
import os


def safe_remove(path):
    os.remove(path)
        """,
        """
import os


def safe_remove(path):
    if os.path.exists(path):
        os.remove(path)
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import safe_remove


class VisibleTests(unittest.TestCase):
    def test_existing(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            name = handle.name
        safe_remove(name)
        self.assertFalse(os.path.exists(name))
        """,
        """
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import safe_remove


class HiddenTests(unittest.TestCase):
    def test_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            safe_remove(os.path.join(tmp, "missing.txt"))
        """,
        ["planning"],
    ),
    _task(
        "cli_parse_pairs",
        "cli_tools",
        "cli_behavior",
        "holdout",
        3,
        "Fix src/app.py so parse_pairs trims whitespace around the key and value in each KEY=VALUE argument.",
        """
def parse_pairs(argv):
    result = {}
    for item in argv:
        key, value = item.split("=")
        result[key] = value
    return result
        """,
        """
def parse_pairs(argv):
    result = {}
    for item in argv:
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_pairs


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_pairs(["a=1"]), {"a": "1"})
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import parse_pairs


class HiddenTests(unittest.TestCase):
    def test_strip(self):
        self.assertEqual(parse_pairs([" a = 1 "]), {"a": "1"})
        """,
        ["planning"],
    ),
    _task(
        "state_merge_counts",
        "state_store",
        "state_handling",
        "train",
        3,
        "Fix src/app.py so merge_counts adds overlapping counts instead of replacing them.",
        """
def merge_counts(left, right):
    merged = dict(left)
    merged.update(right)
    return merged
        """,
        """
def merge_counts(left, right):
    merged = dict(left)
    for key, value in right.items():
        merged[key] = merged.get(key, 0) + value
    return merged
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_counts


class VisibleTests(unittest.TestCase):
    def test_merge(self):
        self.assertEqual(merge_counts({"a": 1}, {"a": 2, "b": 1}), {"a": 3, "b": 1})
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import merge_counts


class HiddenTests(unittest.TestCase):
    def test_new_key(self):
        self.assertEqual(merge_counts({}, {"x": 1}), {"x": 1})
        """,
        ["decomposition"],
    ),
    _task(
        "api_extract_error",
        "api_client",
        "api_client_mocking",
        "train",
        2,
        "Fix src/app.py so error_message falls back to a top-level error field when detail is missing.",
        """
def error_message(response):
    return response["detail"]
        """,
        """
def error_message(response):
    return response.get("detail") or response.get("error", "")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import error_message


class VisibleTests(unittest.TestCase):
    def test_detail(self):
        self.assertEqual(error_message({"detail": "bad"}), "bad")
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import error_message


class HiddenTests(unittest.TestCase):
    def test_error(self):
        self.assertEqual(error_message({"error": "boom"}), "boom")
        """,
        ["planning"],
    ),
    _task(
        "validator_required_list",
        "validator_suite",
        "data_validation",
        "train",
        2,
        "Fix src/app.py so missing_items treats an empty list as missing.",
        """
def missing_items(payload, key):
    return payload.get(key) is None
        """,
        """
def missing_items(payload, key):
    value = payload.get(key)
    return value is None or value == []
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import missing_items


class VisibleTests(unittest.TestCase):
    def test_none(self):
        self.assertTrue(missing_items({}, "items"))
        """,
        """
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from app import missing_items


class HiddenTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertTrue(missing_items({"items": []}, "items"))
        """,
        ["planning"],
    ),
]
