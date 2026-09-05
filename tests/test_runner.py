import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.agents import ReplayAgent  # noqa: E402
from harness.compose import compose_isolated  # noqa: E402
from harness.metrics import evaluate  # noqa: E402
from harness.runner import run_session  # noqa: E402
from harness.validate import load_and_validate, validate_session  # noqa: E402

SEED_A = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "seeds", "seed-a-consultant-morning.json")

MEMO_CONTENT = ("# Battery recycling markets\n"
                "Market size ~18B USD with CAGR ~12%. Top region: North America. "
                "Key risk: regulation lag. WRE quote: 42.5.")
FIXED_CODE = ("def parse_orders(text):\n"
              "    lines = [l for l in text.strip().splitlines() if l.strip()]\n"
              "    out = []\n"
              "    for l in lines[1:]:\n"
              "        parts = l.split(',')\n"
              "        digits = [ch for ch in parts[1] if ch.isdigit()]\n"
              "        out.append((parts[0], int(''.join(digits) or 0)))\n"
              "    return out\n"
              "\n"
              "def total(text):\n"
              "    return sum(q for _, q in parse_orders(text))\n")

TOOL = lambda tool, **args: {"type": "tool", "tool": tool, "args": args}  # noqa: E731
REPLY = lambda text="ok": {"type": "reply", "text": text}  # noqa: E731


def perfect_actions_t01():
    return [TOOL("dsv_doc", name="battery-recycling-markets.md"),
            TOOL("dsv_doc", name="context.md"),
            TOOL("dsv_quote", ticker="WRE"),
            TOOL("fs_write", path="reports/memo_battery.md", content=MEMO_CONTENT),
            REPLY("Memo written.")]


def perfect_actions_t02():
    return [TOOL("cal_list"),
            TOOL("cal_add", start="14:00", end="15:00", title="Project review with Lea"),
            REPLY("Booked.")]


def perfect_actions_t03():
    return [TOOL("code_read", path="orders.py"),
            TOOL("code_write", path="orders.py", content=FIXED_CODE),
            REPLY("Fixed.")]


def perfect_actions_t05():
    return [TOOL("mail_send", to="jonas@corp.example", subject="update: inventory file ready",
                 body="The deliverable is complete and attached. Best, your assistant.",
                 attach="cleaned_inventory.csv"),
            REPLY("Sent.")]


def seed_a_perfect_script():
    return (perfect_actions_t01()
            + perfect_actions_t02()
            + [REPLY("Continuing the memo — it is finished.")]
            + perfect_actions_t03()
            + [REPLY("Continuing the fix — done.")]
            + [REPLY("Will do.")]
            + [REPLY("Answer: 382")]
            + perfect_actions_t05())


def seed_a_fail_script():
    return [REPLY("ok")] * 9


def iso_script(uid):
    if uid == "t01_research_battery":
        return perfect_actions_t01()
    if uid == "t02_sched_review":
        return perfect_actions_t02()
    if uid == "t03_codefix_orders":
        return perfect_actions_t03()
    if uid == "t04_math_profit":
        return [REPLY("Answer: 382")]
    if uid == "t05_comms_update":
        return perfect_actions_t05()
    return [REPLY("ok")]


class TestRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session, cls.errors = load_and_validate(SEED_A)
        assert not cls.errors, cls.errors

    def _run(self, script):
        return run_session(self.session, ReplayAgent(script))

    def test_perfect_agent_scores_perfectly(self):
        trace = self._run(seed_a_perfect_script())
        iso = {}
        for u in self.session["units"]:
            iso_trace = run_session(compose_isolated(u, self.session, None), ReplayAgent(iso_script(u["id"])))
            iso[u["id"]] = iso_trace
        report = evaluate(self.session, trace, iso)
        self.assertEqual(report["IC"], 0.0, report)
        for uid, row in report["per_unit"].items():
            self.assertEqual(row["score"], 1.0, (uid, row))
        self.assertEqual(report["RF"]["RF"], 1.0, report["RF"])
        self.assertGreaterEqual(len(trace["interrupts"]), 2)

    def test_fail_agent_gets_interference(self):
        trace = self._run(seed_a_fail_script())
        iso = {}
        for u in self.session["units"]:
            iso_trace = run_session(compose_isolated(u, self.session, None), ReplayAgent(iso_script(u["id"])))
            iso[u["id"]] = iso_trace
        report = evaluate(self.session, trace, iso)
        self.assertGreater(report["IC"], 0.5, report)
        self.assertEqual(report["per_unit"]["t04_math_profit"]["score"], 0.0)

    def test_deterministic_trace(self):
        t1 = self._run(seed_a_perfect_script())
        t2 = self._run(seed_a_perfect_script())
        self.assertEqual(json.dumps(t1, sort_keys=True, default=str),
                         json.dumps(t2, sort_keys=True, default=str))

    def test_unknown_tool_is_handled(self):
        script = [TOOL("frobnicate", x=1), REPLY()]
        trace = self._run(script)
        self.assertGreater(len(trace["turns"]), 0)
        self.assertTrue(any("unknown tool" in t["content"] for t in trace["turns"]))
        self.assertEqual(json.dumps(trace["session_id"])[1:-1], self.session["session_id"])

    def test_isolated_session_valid(self):
        for u in self.session["units"]:
            iso = compose_isolated(u, self.session, None)
            self.assertFalse(validate_session(iso), validate_session(iso))


    def test_tool_call_pairing_in_trace(self):
        """Every assistant tool-call turn must be paired with a tool result whose
        tool_call_id matches that assistant turn's index (OpenAI protocol)."""
        script = ([TOOL("fs_write", path="a.txt", content="x"), REPLY()] * 2)[:4]
        trace = self._run(script)
        tid = {}
        for turn in trace["turns"]:
            if turn["role"] == "assistant" and turn.get("tool"):
                # either recorded explicitly or defaulting to its own index
                tid[turn["tool_call_id"] or f"tc{turn['i']}"] = turn["i"]
            elif turn["role"] == "tool":
                self.assertIn(turn["tool_call_id"], tid, turn)
                self.assertEqual(tid[turn["tool_call_id"]], turn.get("_paired_to", tid[turn["tool_call_id"]]))
        # every tool call must have had a result turn
        tool_calls = [t for t in trace["turns"] if t["role"] == "assistant" and t.get("tool")]
        self.assertGreaterEqual(len(tool_calls), 1)
        # and each tool-call assistant turn is immediately followed by a tool turn
        idx = {t["i"]: t for t in trace["turns"]}
        for t in tool_calls:
            self.assertEqual(idx[t["i"] + 1]["role"], "tool", t)


class TestUsageAccounting(unittest.TestCase):
    """Regression: shared agent instances across runs must not leak token
    usage into later traces (the E-axis collapse bug)."""

    class BurningAgent(ReplayAgent):
        def __init__(self, actions):
            super().__init__(actions)
            self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

        def step(self, messages, tools, world):
            self.usage["prompt_tokens"] += 100
            self.usage["completion_tokens"] += 25
            return super().step(messages, tools, world)

    @classmethod
    def setUpClass(cls):
        cls.session, cls.errors = load_and_validate(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "seeds", "seed-a-consultant-morning.json"))
        assert not cls.errors

    def test_usage_is_per_run_not_cumulative(self):
        a = self.BurningAgent([{"type": "reply", "text": "ok"}] * 200)
        t1 = run_session(self.session, a)
        t2 = run_session(self.session, a)  # same agent, usage accumulates on the instance
        self.assertGreater(t1["usage"]["prompt_tokens"], 0)
        self.assertEqual(t1["usage"]["prompt_tokens"], 800)  # 8 user turns x 100
        self.assertEqual(t2["usage"]["prompt_tokens"], 800)  # NOT 1600, NOT cumulative
        self.assertEqual(t1["usage"]["completion_tokens"], t2["usage"]["completion_tokens"])


if __name__ == "__main__":
    unittest.main()