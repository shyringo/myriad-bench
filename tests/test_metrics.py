import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.agents import ReplayAgent  # noqa: E402
from harness.metrics import (budget_efficiency, evaluate, resume_fidelity,  # noqa: E402
                             retention_map, state_web, switch_cost)
from harness.runner import run_session  # noqa: E402

TOOL = lambda name, **args: {"type": "tool", "tool": name, "args": args}  # noqa: E731
REPLY = lambda text="ok": {"type": "reply", "text": text}  # noqa: E731


def make_session(units, events, world=None):
    return {
        "schema_version": "0.1.0",
        "session_id": "test-session",
        "kind": "mixed",
        "isolated_unit": None,
        "meta": {"name": "t", "tier": "S", "seed": 1, "mixture": {"K": len(units), "H": 0.5, "D": 0.5, "DEP": 0.5, "IR": 0.5, "NV": 0}},
        "world": world or {"fs": {"kind": "fs", "state": {"files": {}}}},
        "units": units,
        "events": events,
    }


def fs_unit(uid, verifier, brief="do the thing", extra=None):
    u = {"id": uid, "family": "test_fam", "title": uid, "brief": brief, "tools": ["fs"],
         "verifier": verifier, "priority": 1, "time_budget_min": 5, "rarity": 1,
         "interruptible": True, "produce_artifacts": [], "checkpoints": []}
    if extra:
        u.update(extra)
    return u


def assign(uid, at="10:00"):
    return {"id": f"e-{uid}", "kind": "assign", "at": at, "unit": uid, "payload": {"user": "task", "background": ""}}


class TestStateWeb(unittest.TestCase):
    def _run_pair(self, consumer_read=True):
        p = fs_unit("p", {"type": "file_created", "config": {"path": "fs/a.txt"}},
                    extra={"produce_artifacts": ["fs/a.txt"]})
        c = fs_unit("c", {"type": "file_created", "config": {"path": "fs/b.txt"}},
                    brief="read a.txt then write b.txt",
                    extra={"depends_on": [{"unit": "p", "artifact": "fs/a.txt"}]})
        s = make_session([p, c], [assign("p", "09:00"), assign("c", "09:30")])
        p_script = [TOOL("fs_write", path="a.txt", content="hello"), REPLY()]
        if consumer_read:
            c_script = [TOOL("fs_read", path="a.txt"), TOOL("fs_write", path="b.txt", content="hi"), REPLY()]
        else:
            c_script = [TOOL("fs_write", path="b.txt", content="hi-no-read"), REPLY()]
        trace = run_session(s, ReplayAgent(p_script + c_script))
        return state_web(s, trace)

    def test_obligation_satisfied(self):
        r = self._run_pair(consumer_read=True)
        self.assertEqual(r["SWC"], 1.0, r)
        self.assertTrue(r["obligations"][0]["ok"])

    def test_obligation_violated_without_consumption(self):
        r = self._run_pair(consumer_read=False)
        self.assertEqual(r["SWC"], 0.0, r)
        self.assertFalse(r["obligations"][0]["ok"])


class TestResumeFidelity(unittest.TestCase):
    def _run(self, resumed_content):
        u = fs_unit("u", {"type": "file_created", "config": {"path": "fs/x.txt"}},
                    extra={"produce_artifacts": ["fs/x.txt"]})
        events = [assign("u", "09:00"),
                  {"id": "e-int", "kind": "interrupt", "at": "09:10", "unit": "u", "payload": {"reason": "ping"}},
                  {"id": "e-res", "kind": "resume", "at": "09:12", "unit": "u", "payload": {"note": "cont"}},
                  {"id": "e-done", "kind": "done", "at": "09:20", "unit": None, "payload": None}]
        s = make_session([u], events)
        script = [TOOL("fs_write", path="x.txt", content="V1"), REPLY(),
                  TOOL("fs_write", path="x.txt", content=resumed_content), REPLY()]
        mixed = run_session(s, ReplayAgent(script))
        iso_s = make_session([u], [assign("u"), {"id": "e-d", "kind": "done", "at": "10:00", "unit": None, "payload": None}])
        iso = run_session(iso_s, ReplayAgent([TOOL("fs_write", path="x.txt", content="V1"), REPLY()]))
        return resume_fidelity(s, mixed, {"u": iso})

    def test_state_kept_across_interruption(self):
        r = self._run("V1")
        self.assertEqual(r["RF"], 1.0, r)

    def test_state_drift_detected(self):
        r = self._run("V2-DRIFTED")
        self.assertEqual(r["RF"], 0.0, r)


class TestSwitchCost(unittest.TestCase):
    def test_late_milestone_costs(self):
        a = fs_unit("a", {"type": "file_created", "config": {"path": "fs/a.txt"}})
        b = fs_unit("b", {"type": "file_created", "config": {"path": "fs/b.txt"}},
                    extra={"family": "beta_fam",
                           "checkpoints": [{"type": "file_created", "config": {"path": "fs/b.txt"}, "id": "cp"}]})
        s = make_session([a, b], [assign("a", "09:00"), assign("b", "09:30")])
        # B stalls: reads, then writes the milestone, then replies
        script = [TOOL("fs_write", path="a.txt", content="A"), REPLY(),
                  TOOL("fs_read", path="a.txt"), TOOL("fs_read", path="a.txt"),
                  TOOL("fs_read", path="a.txt"), TOOL("fs_read", path="a.txt"),
                  TOOL("fs_write", path="b.txt", content="B"), REPLY()]
        trace = run_session(s, ReplayAgent(script))
        r = switch_cost(s, trace, tau=3)
        self.assertEqual(r["SC"], 1.0, r)
        self.assertEqual(r["SC_first"], 1.0, r)

    def test_immediate_milestone_costs_nothing(self):
        a = fs_unit("a", {"type": "file_created", "config": {"path": "fs/a.txt"}})
        b = fs_unit("b", {"type": "file_created", "config": {"path": "fs/b.txt"}},
                    extra={"checkpoints": [{"type": "file_created", "config": {"path": "fs/b.txt"}, "id": "cp"}]})
        s = make_session([a, b], [assign("a", "09:00"), assign("b", "09:30")])
        script = [TOOL("fs_write", path="a.txt", content="A"), REPLY(),
                  TOOL("fs_write", path="b.txt", content="B"), REPLY()]
        trace = run_session(s, ReplayAgent(script))
        # segment of b = 2 turns < 2*tau -> skipped, SC None
        r = switch_cost(s, trace, tau=3)
        self.assertIsNone(r["SC"])


class TestAggregates(unittest.TestCase):
    def test_retention_map(self):
        mixed = {"u1": {"score": 0.8, "family": "f", "rarity": 1}}
        iso = {"u1": {"score": 0.9}}
        self.assertAlmostEqual(retention_map(mixed, iso)["u1"], 0.8 / 0.9)

    def test_budget_efficiency_estimator(self):
        u = fs_unit("u", {"type": "file_created", "config": {"path": "fs/a.txt"}})
        s = make_session([u], [assign("u")])
        trace = run_session(s, ReplayAgent([TOOL("fs_write", path="a.txt", content="x"), REPLY()]))
        r = budget_efficiency(s, trace, {"u": {"score": 1.0}})
        self.assertGreater(r["BE"], 0)
        self.assertTrue(r["estimated"])

    def test_evaluate_full_pipeline(self):
        u = fs_unit("u", {"type": "file_created", "config": {"path": "fs/a.txt"}},
                    extra={"produce_artifacts": ["fs/a.txt"], "rarity": 4})
        s = make_session([u], [assign("u")])
        mixed = run_session(s, ReplayAgent([TOOL("fs_write", path="a.txt", content="x"), REPLY()]))
        iso_s = make_session([u], [assign("u"), {"id": "d", "kind": "done", "at": "12:00", "unit": None, "payload": None}])
        iso = run_session(iso_s, ReplayAgent([TOOL("fs_write", path="a.txt", content="x"), REPLY()]))
        report = evaluate(s, mixed, {"u": iso})
        self.assertEqual(report["IC"], 0.0)
        self.assertEqual(report["LTR"]["LTR"]["4"], 1.0)
        self.assertIsNone(report["SWC"]["SWC"])  # no obligations declared


class TestMyriadIndex(unittest.TestCase):
    def _run_pair(self, mixed_script, unit_script):
        u = fs_unit("u", {"type": "file_created", "config": {"path": "fs/a.txt"}},
                    extra={"produce_artifacts": ["fs/a.txt"], "rarity": 4})
        s = make_session([u], [assign("u")])
        iso_s = make_session([u], [assign("u"), {"id": "d", "kind": "done", "at": "12:00", "unit": None, "payload": None}])
        mixed = run_session(s, ReplayAgent(mixed_script))
        iso = run_session(iso_s, ReplayAgent(unit_script))
        return evaluate(s, mixed, {"u": iso})

    def test_perfect_agent_scores_high_wji(self):
        r = self._run_pair([TOOL("fs_write", path="a.txt", content="x"), REPLY()],
                           [TOOL("fs_write", path="a.txt", content="x"), REPLY()])
        self.assertEqual(r["status"], "ok")
        self.assertGreaterEqual(r["MI"], 90.0, r)

    def test_failing_agent_scores_low_wji(self):
        r = self._run_pair([REPLY("nope")],
                           [TOOL("fs_write", path="a.txt", content="x"), REPLY()])
        self.assertLess(r["MI"], 15.0, r)

    def test_wji_without_isolated_is_invalid(self):
        u = fs_unit("u", {"type": "file_created", "config": {"path": "fs/a.txt"}})
        s = make_session([u], [assign("u")])
        mixed = run_session(s, ReplayAgent([TOOL("fs_write", path="a.txt", content="x"), REPLY()]))
        report = evaluate(s, mixed, {})
        self.assertEqual(report["status"], "no_isolated")
        self.assertIsNone(report["MI"])


if __name__ == "__main__":
    unittest.main()