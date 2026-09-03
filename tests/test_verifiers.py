import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.envs import World  # noqa: E402
from harness.verifiers import verify  # noqa: E402

UNIT = {"id": "u", "family": "x", "title": "t", "brief": "b", "tools": [], "priority": 1,
        "time_budget_min": 1, "rarity": 1}
TRACE = {"turns": [], "reads": [], "unit_reply": {}}


def world_with(fs_files=None, calendar=None, sent=None, code_files=None):
    spec = {}
    if fs_files is not None:
        spec["fs"] = {"kind": "fs", "state": {"files": fs_files}}
    if calendar is not None:
        spec["calendar"] = {"kind": "calendar", "state": {"owner": "me", "events": calendar}}
    if sent is not None:
        spec["email"] = {"kind": "email", "state": {"sent": sent, "inbox": []}}
    if code_files is not None:
        spec["code"] = {"kind": "code", "state": {"files": code_files}}
    return World(spec)


class TestVerifiers(unittest.TestCase):
    def test_file_created(self):
        w = world_with(fs_files={"a.md": "hi"})
        r = verify(w, UNIT, TRACE, {}, {"type": "file_created", "config": {"path": "fs/a.md"}})
        self.assertEqual(r["score"], 1.0)
        r = verify(w, UNIT, TRACE, {}, {"type": "file_created", "config": {"path": "fs/missing.md"}})
        self.assertEqual(r["score"], 0.0)

    def test_file_contains_partial(self):
        w = world_with(fs_files={"a.md": "CAGR 12% North America"})
        r = verify(w, UNIT, TRACE, {}, {"type": "file_contains",
                                        "config": {"path": "fs/a.md", "patterns": ["CAGR", "zzz"]}})
        self.assertEqual(r["score"], 0.5)

    def test_numeric_assert_reply(self):
        ctx = {"final_reply": "Answer: 382", "artifacts": {}}
        r = verify(world_with(), UNIT, TRACE, ctx, {"type": "numeric_assert",
                                                    "config": {"source": "reply",
                                                               "rows": [{"op": "eq", "value": 382, "tol": 0.5}]}})
        self.assertEqual(r["score"], 1.0)
        ctx["final_reply"] = "the answer is definitely 381"
        r = verify(world_with(), UNIT, TRACE, ctx, {"type": "numeric_assert",
                                                    "config": {"source": "reply",
                                                               "rows": [{"op": "eq", "value": 382, "tol": 0.5}]}})
        self.assertEqual(r["score"], 0.0)

    def test_calendar_invariant_overlap(self):
        w = world_with(calendar=[{"start": "09:00", "end": "10:00", "title": "A"},
                                 {"start": "09:30", "end": "10:30", "title": "B"}])
        r = verify(w, UNIT, TRACE, {}, {"type": "calendar_invariant",
                                        "config": {"no_overlap": True, "requires_events": []}})
        self.assertEqual(r["score"], 0.0)
        w2 = world_with(calendar=[{"start": "09:00", "end": "09:30", "title": "A"}])
        r = verify(w2, UNIT, TRACE, {}, {"type": "calendar_invariant",
                                         "config": {"no_overlap": True, "requires_events": []}})
        self.assertEqual(r["score"], 1.0)

    def test_email_checks(self):
        w = world_with(sent=[{"to": "x@y.z", "subject": "update: f", "body": "deliverable done", "cc": "", "attach": "f.csv"}])
        r = verify(w, UNIT, TRACE, {}, {"type": "email_checks", "config": {"requires": [
            {"to": "x@y.z", "subject_sub": "update", "body_sub": "deliverable", "attach_sub": "f.csv"}]}})
        self.assertEqual(r["score"], 1.0)

    def test_code_passes(self):
        good = "def f(x):\n    return x + 1\n"
        bad = "def f(x):\n    return x  # wrong\n"
        tests = "assert f(1) == 2\nprint('ALL_TESTS_PASSED')\n"
        cfg = {"type": "code_passes", "config": {"file": "code/m.py", "hidden_tests": tests,
                                                 "marker": "ALL_TESTS_PASSED"}}
        w = world_with(code_files={"m.py": good})
        self.assertEqual(verify(w, UNIT, TRACE, {}, cfg)["score"], 1.0)
        w = world_with(code_files={"m.py": bad})
        self.assertEqual(verify(w, UNIT, TRACE, {}, cfg)["score"], 0.0)

    def test_csv_rows_match(self):
        w = world_with(fs_files={"d.csv": "id,qty\nitem0,100\nitem1,110\n"})
        r = verify(w, UNIT, TRACE, {}, {"type": "csv_rows_match",
                                        "config": {"path": "fs/d.csv",
                                                   "must_include_rows": [{"id": "item0", "qty": "100"}],
                                                   "total_rows_expected": 2}})
        self.assertEqual(r["score"], 1.0)
        r = verify(w, UNIT, TRACE, {}, {"type": "csv_rows_match",
                                        "config": {"path": "fs/d.csv",
                                                   "must_include_rows": [{"id": "item9"}],
                                                   "total_rows_expected": 2}})
        self.assertEqual(r["score"], 0.5)

    def test_state_web(self):
        w = world_with(fs_files={"a.txt": "hello"})
        ctx = {"artifacts": {"fs/a.txt": "hash_of_hello"}, "final_reply": ""}
        r = verify(w, UNIT, TRACE, ctx, {"type": "state_web",
                                         "config": {"obligation": {"unit": "p", "artifact": "fs/a.txt"}}})
        # certified hash won't match the real content hash -> fails
        self.assertEqual(r["score"], 0.0)
        from harness.envs import stable_hash
        ctx["artifacts"] = {"fs/a.txt": stable_hash("hello")}
        w._reads = [{"env": "fs", "key": "fs/a.txt", "unit": "u", "ts": 0}]
        r = verify(w, UNIT, TRACE, ctx, {"type": "state_web",
                                         "config": {"obligation": {"unit": "p", "artifact": "fs/a.txt"}}})
        self.assertEqual(r["score"], 1.0)


if __name__ == "__main__":
    unittest.main()